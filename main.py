"""
Точка входа для запуска агента.
Минимальная версия: создание контекстов и запуск агента.
"""
import asyncio
import sys
import warnings

# Подавляем предупреждения Pydantic о не-JSON сериализуемых значениях по умолчанию
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig

# === ВОПРОСЫ ДЛЯ ТЕСТИРОВАНИЯ ===
GOAL = "Какие книги написал Александр Пушкин?"
MAX_STEPS = 10  # Увеличено для полного выполнения
TEMPERATURE = 0.7


async def run_agent(goal: str, max_steps: int = None, temperature: float = None) -> str:
    """Запуск агента с заданной целью."""
    import traceback
    
    # Загрузка конфигурации
    config = get_config(profile='dev')

    # Создание и инициализация инфраструктурного контекста
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    try:
        # Создание прикладного контекста (один на всё приложение)
        # ИСПОЛЬЗУЕМ from_registry для загрузки конфигурации из registry.yaml
        app_config = AppConfig.from_registry(profile="prod")
        
        # Проверяем, что содержит app_config до инициализации
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"MAIN: app_config.service_configs={list(getattr(app_config, 'service_configs', {}).keys())}, app_config.skill_configs={list(getattr(app_config, 'skill_configs', {}).keys())}, app_config.tool_configs={list(getattr(app_config, 'tool_configs', {}).keys())}")
        
        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )
        
        # Проверяем data_repository до инициализации
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"MAIN: До инициализации - use_data_repository={application_context.use_data_repository}, data_repository={application_context.data_repository}")
        
        await application_context.initialize()

        # Подписка на события LLM для логирования
        from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
        llm_subscriber = LLMEventSubscriber(log_full_content=False)  # True для полного логирования
        llm_subscriber.subscribe(application_context.event_bus)
        logger.info("Подписчик на события LLM активирован")

        # Проверяем, что компоненты зарегистрированы
        from core.models.enums.common_enums import ComponentType
        logger.error(f"MAIN: После инициализации - use_data_repository={application_context.use_data_repository}, data_repository={application_context.data_repository}")
        logger.error(f"MAIN: После инициализации - SKILL={list(application_context.components._components[ComponentType.SKILL].keys())}, TOOL={list(application_context.components._components[ComponentType.TOOL].keys())}")

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
        print(f"\nОшибка в run_agent: {e}")
        traceback.print_exc()
        raise
    finally:
        # Завершение работы инфраструктурного контекста
        await infrastructure_context.shutdown()


def main() -> int:
    """Точка входа."""
    import traceback

    try:
        result = asyncio.run(run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE
        ))

        print("\nРезультат:")
        print(result)
        return 0

    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        return 0
    except Exception as e:
        print(f"\nОшибка в main: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
