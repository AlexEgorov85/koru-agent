"""
Точка входа для запуска агента.
Минимальная версия: создание контекстов и запуск агента.
"""
import asyncio
import sys
import warnings
import logging
import os

# Подавляем предупреждения Pydantic о не-JSON сериализуемых значениях по умолчанию
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig
import logging

# === ВОПРОСЫ ДЛЯ ТЕСТИРОВАНИЯ ===
GOAL = "Какие книги написал Александр Пушкин?"
MAX_STEPS = 10  # Увеличено для полного выполнения
TEMPERATURE = 0.7


def setup_logging_from_config():
    """
    Настройка логирования из конфигурации.
    
    Консоль: WARNING+ (ошибки) + koru.main INFO (пользовательские сообщения)
    Файл: DEBUG+ (все технические детали, включая промпты и ответы)
    Сессии: logs/sessions/{session_id}.log (все LLM вызовы + техника)
    """
    from core.infrastructure.logging.log_formatter import setup_logging, LogFormatter
    from core.infrastructure.logging.session_logger import cleanup_old_sessions
    import yaml
    
    # Создаём директорию для логов
    os.makedirs("logs", exist_ok=True)
    os.makedirs("logs/sessions", exist_ok=True)
    
    # Читаем конфигурацию логирования из YAML
    module_levels = {}
    try:
        with open("core/config/logging_config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if config and 'logging' in config:
                logging_config = config['logging']
                
                # Получаем уровни для модулей
                if 'module_levels' in logging_config:
                    level_map = {
                        'DEBUG': logging.DEBUG,
                        'INFO': logging.INFO,
                        'WARNING': logging.WARNING,
                        'ERROR': logging.ERROR,
                        'CRITICAL': logging.CRITICAL
                    }
                    for module_name, level_str in logging_config['module_levels'].items():
                        if isinstance(level_str, str):
                            module_levels[module_name] = level_map.get(level_str.upper(), logging.INFO)
                        else:
                            module_levels[module_name] = level_str
    except Exception:
        pass
    
    # Очищаем старые сессии (max 100)
    cleanup_old_sessions(max_sessions=100, log_dir="logs/sessions")
    
    # Настраиваем базовое логирование
    root_logger = setup_logging(
        level=logging.WARNING,  # Консоль - только WARNING+
        format_type="text",
        log_file="logs/agent.log",
        log_file_max_size=10485760,
        log_file_backup_count=5,
        use_colors=True,
        module_levels=module_levels
    )
    
    # Добавляем консольный обработчик для пользовательских сообщений (koru.main)
    formatter = LogFormatter(format_type="text", use_colors=True)
    console_info_handler = logging.StreamHandler()
    console_info_handler.setLevel(logging.INFO)
    console_info_handler.setFormatter(formatter)
    
    # Настраиваем koru.main для вывода в консоль
    main_logger = logging.getLogger("koru.main")
    main_logger.setLevel(logging.INFO)
    main_logger.addHandler(console_info_handler)
    main_logger.propagate = False  # Не дублировать в корневой
    
    # Настраиваем koru.agent для вывода в консоль
    agent_logger = logging.getLogger("koru.agent")
    agent_logger.setLevel(logging.INFO)
    agent_logger.addHandler(console_info_handler)
    agent_logger.propagate = False


async def run_agent(goal: str, max_steps: int = None, temperature: float = None) -> str:
    """Запуск агента с заданной целью."""
    import traceback
    from core.infrastructure.logging.session_logger import get_session_logger, close_session_logger

    # Инициализация логгера
    logger = logging.getLogger("main")

    # Загрузка конфигурации
    config = get_config(profile='dev')

    # Создание и инициализация инфраструктурного контекста
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    
    # Получаем session_id для логгера сессии
    session_id = str(infrastructure_context.id)
    session_logger = get_session_logger(session_id)

    try:
        # Создание прикладного контекста (один на всё приложение)
        # ИСПОЛЬЗУЕМ from_registry для загрузки конфигурации из registry.yaml
        app_config = AppConfig.from_registry(profile="prod")

        # Проверяем, что содержит app_config до инициализации
        logger.debug(f"app_config.service_configs={list(getattr(app_config, 'service_configs', {}).keys())}, app_config.skill_configs={list(getattr(app_config, 'skill_configs', {}).keys())}, app_config.tool_configs={list(getattr(app_config, 'tool_configs', {}).keys())}")

        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        # Проверяем data_repository до инициализации
        logger.debug(f"До инициализации - use_data_repository={application_context.use_data_repository}, data_repository={application_context.data_repository}")

        await application_context.initialize()

        # Подписка на события LLM для логирования
        # log_full_content=True → полные промпты/ответы пишутся в файл сессии
        from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
        llm_subscriber = LLMEventSubscriber(log_full_content=True)
        llm_subscriber.subscribe(application_context.infrastructure_context.event_bus)
        logger.debug("Подписчик на события LLM активирован")
        
        # Подписка на события для логирования в сессию
        from core.infrastructure.event_bus.session_log_handler import init_session_logging
        init_session_logging(application_context.infrastructure_context.event_bus, session_id)
        logger.debug("SessionLogHandler активирован")

        # Проверяем, что компоненты зарегистрированы
        from core.models.enums.common_enums import ComponentType
        logger.debug(f"После инициализации - use_data_repository={application_context.use_data_repository}, data_repository={application_context.data_repository}")
        logger.debug(f"После инициализации - SKILL={list(application_context.components._components[ComponentType.SKILL].keys())}, TOOL={list(application_context.components._components[ComponentType.TOOL].keys())}")

        # Создание фабрики агентов
        agent_factory = AgentFactory(application_context)

        # Подготовка конфигурации агента
        agent_config_kwargs = {}
        if max_steps is not None:
            agent_config_kwargs['max_steps'] = max_steps
        if temperature is not None:
            agent_config_kwargs['temperature'] = temperature

        agent_config = AgentConfig(**agent_config_kwargs) if agent_config_kwargs else None

        # Создание и запуск агента
        agent = await agent_factory.create_agent(
            goal=goal,
            config=agent_config
        )

        result = await agent.run(goal)

        # Проверка на ошибку в результате
        if hasattr(result, 'metadata') and result.metadata and 'error' in result.metadata:
            error_msg = result.metadata['error']
            raise RuntimeError(f"Ошибка агента: {error_msg}")

        return result

    except Exception as e:
        logger.error(f"Ошибка в run_agent: {e}", exc_info=True)
        session_logger.error(f"Ошибка: {e}", exc_info=True)
        raise
    finally:
        # Завершение работы инфраструктурного контекста
        await infrastructure_context.shutdown()
        
        # Закрываем логгер сессии
        close_session_logger(session_id)


def main() -> int:
    """Точка входа."""
    import traceback

    # Настройка логирования
    setup_logging_from_config()

    # Инициализация логгера
    logger = logging.getLogger("main")

    try:
        # Пользователь видит начало работы
        logger.info(f"Анализирую вопрос: {GOAL}")
        
        result = asyncio.run(run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE
        ))

        # Пользователь видит результат
        logger.info("\n" + "="*60)
        logger.info("✅ ОТВЕТ:")
        logger.info("="*60)
        # Краткий вывод результата
        result_text = str(result)[:500] if len(str(result)) > 500 else str(result)
        logger.info(f"✅ Результат: {result_text}")

        # Полный результат → в файл (DEBUG)
        logger.debug(f"Полный результат: {result}")
        if hasattr(result, 'metadata'):
            logger.debug(f"Метрики: {result.metadata}")

        return 0

    except KeyboardInterrupt:
        logger.info("\n⏸️ Прервано пользователем")
        return 0
    except Exception as e:
        logger.error(f"❌ Произошла ошибка: {str(e)[:200]}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
