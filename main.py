"""
Точка входа для запуска агента.

Использует новую систему логирования через LogManager.
"""
import asyncio
import sys
import warnings
import logging
import os

# Подавляем предупреждения Pydantic
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig

# === ВОПРОСЫ ДЛЯ ТЕСТИРОВАНИЯ ===
GOAL = "Какие книги написал Александр Пушкин?"
MAX_STEPS = 10
TEMPERATURE = 0.7


def setup_logging_from_config():
    """
    Настройка логирования из конфигурации.
    
    Использует новую систему логирования через LogManager.
    """
    from core.infrastructure.logging import LogFormatter, setup_logging
    import yaml

    # Создаём директорию для логов
    os.makedirs("logs", exist_ok=True)

    # Читаем конфигурацию логирования из YAML
    module_levels = {}
    try:
        with open("core/config/logging_config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if config and 'logging' in config:
                logging_config = config['logging']
                
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

    # Настраиваем базовое логирование
    root_logger = setup_logging(
        level=logging.WARNING,
        format_type="text",
        log_file="logs/agent.log",
        log_file_max_size=10485760,
        log_file_backup_count=5,
        use_colors=True,
        module_levels=module_levels
    )

    # Консольный обработчик для пользовательских сообщений
    formatter = LogFormatter(format_type="text", use_colors=True)
    console_info_handler = logging.StreamHandler()
    console_info_handler.setLevel(logging.INFO)
    console_info_handler.setFormatter(formatter)

    main_logger = logging.getLogger("koru.main")
    main_logger.setLevel(logging.INFO)
    main_logger.addHandler(console_info_handler)
    main_logger.propagate = False

    agent_logger = logging.getLogger("koru.agent")
    agent_logger.setLevel(logging.INFO)
    agent_logger.addHandler(console_info_handler)
    agent_logger.propagate = False


async def run_agent(goal: str, max_steps: int = None, temperature: float = None) -> str:
    """Запуск агента с заданной целью."""
    from core.infrastructure.logging import (
        init_logging_system,
        shutdown_logging_system,
        get_session_logger,
        close_session_logger,
    )

    logger = logging.getLogger("main")

    # Загрузка конфигурации
    config = get_config(profile='dev')

    # Инициализация системы логирования
    await init_logging_system()
    logger.debug("Система логирования инициализирована")

    # Создание и инициализация инфраструктурного контекста
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    # Получаем session_id и создаём логгер сессии
    session_id = str(infrastructure_context.id)
    session_logger = get_session_logger(session_id, agent_id="agent_001")

    try:
        # Начало сессии
        await session_logger.start(goal=goal)
        logger.info(f"Сессия начата: {session_id}")

        # Создание прикладного контекста
        app_config = AppConfig.from_registry(profile="prod")
        logger.debug(f"app_config loaded: service_configs={list(getattr(app_config, 'service_configs', {}).keys())}")

        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        await application_context.initialize()
        logger.debug("ApplicationContext инициализирован")

        # Подписка на события LLM для логирования через SessionLogger
        from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
        llm_subscriber = LLMEventSubscriber(log_full_content=True)
        llm_subscriber.subscribe(application_context.infrastructure_context.event_bus)
        logger.debug("LLMEventSubscriber активирован")

        # Проверка компонентов
        from core.models.enums.common_enums import ComponentType
        logger.debug(f"Компоненты: SKILL={list(application_context.components._components[ComponentType.SKILL].keys())}")

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
        agent = await agent_factory.create_agent(goal=goal, config=agent_config)
        result = await agent.run(goal)

        # Проверка на ошибку
        if hasattr(result, 'metadata') and result.metadata and 'error' in result.metadata:
            error_msg = result.metadata['error']
            await session_logger.log_error("AgentError", error_msg)
            raise RuntimeError(f"Ошибка агента: {error_msg}")

        # Завершение сессии успешно
        await session_logger.end(success=True, result=str(result)[:500])
        logger.info(f"Сессия завершена успешно: {session_id}")

        return result

    except Exception as e:
        logger.error(f"Ошибка в run_agent: {e}", exc_info=True)
        await session_logger.log_error(type(e).__name__, str(e))
        await session_logger.end(success=False, result=str(e))
        raise

    finally:
        # Завершение работы
        close_session_logger(session_id)
        await shutdown_logging_system()
        await infrastructure_context.shutdown()
        logger.debug("Ресурсы освобождены")


def main() -> int:
    """Точка входа."""
    # Настройка логирования
    setup_logging_from_config()

    logger = logging.getLogger("main")

    try:
        logger.info(f"Анализирую вопрос: {GOAL}")

        result = asyncio.run(run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE
        ))

        logger.info("\n" + "="*60)
        logger.info("✅ ОТВЕТ:")
        logger.info("="*60)
        
        result_text = str(result)[:500] if len(str(result)) > 500 else str(result)
        logger.info(f"✅ Результат: {result_text}")
        logger.debug(f"Полный результат: {result}")

        return 0

    except KeyboardInterrupt:
        logger.info("\n⏸️ Прервано пользователем")
        return 0
    except Exception as e:
        logger.error(f"❌ Произошла ошибка: {str(e)[:200]}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
