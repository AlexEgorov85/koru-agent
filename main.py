"""
Точка входа для запуска агента.

Использует новую систему логирования через EventBus.
"""
import asyncio
import sys
import warnings
import logging

# Подавляем предупреждения Pydantic
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig

# === ВОПРОСЫ ДЛЯ ТЕСТИРОВАНИЯ ===
GOAL = "Сколько будет 2 + 2?"
MAX_STEPS = 10
TEMPERATURE = 0.7


async def run_agent(goal: str, max_steps: int = None, temperature: float = None) -> str:
    """Запуск агента с заданной целью."""
    from core.infrastructure.logging import (
        init_logging_system,
        shutdown_logging_system,
        get_session_logger,
    )

    # Инициализация системы логирования через EventBus
    await init_logging_system()
    logger = logging.getLogger("main")
    logger.debug("Система логирования инициализирована")

    # Загрузка конфигурации приложения
    config = get_config(profile='dev')

    # Создание и инициализация инфраструктурного контекста
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    # Получаем session_id и создаём логгер сессии
    session_id = str(infrastructure_context.id)
    session_logger = get_session_logger(session_id, agent_id="agent_001")

    try:
        # Начало сессии
        await session_logger.start_session(goal=goal)
        await session_logger.info(f"Сессия начата: {session_id}")

        # Создание прикладного контекста
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        await session_logger.debug(f"app_config loaded via discovery")

        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        await application_context.initialize()
        await session_logger.info("✅ ApplicationContext инициализирован")

        # DEBUG: Проверка что компоненты загрузились
        from core.models.enums.common_enums import ComponentType
        skill_count = len(application_context.components._components.get(ComponentType.SKILL, {}))
        await session_logger.info(f"✅ Загружено навыков: {skill_count}")

        # Подписка на события LLM
        from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
        llm_subscriber = LLMEventSubscriber(log_full_content=True)
        llm_subscriber.subscribe(application_context.infrastructure_context.event_bus)
        await session_logger.info("✅ LLMEventSubscriber активирован")

        # Создание фабрики агентов
        agent_factory = AgentFactory(application_context)
        await session_logger.info("✅ AgentFactory создан")

        # Подготовка конфигурации агента
        agent_config_kwargs = {}
        if max_steps is not None:
            agent_config_kwargs['max_steps'] = max_steps
        if temperature is not None:
            agent_config_kwargs['temperature'] = temperature

        agent_config = AgentConfig(**agent_config_kwargs) if agent_config_kwargs else None
        await session_logger.info("✅ AgentConfig создан")

        # Создание и запуск агента
        await session_logger.info("🔄 Создание агента...")
        agent = await agent_factory.create_agent(goal=goal, config=agent_config)
        await session_logger.info(f"✅ Агент создан: {type(agent).__name__}")

        await session_logger.info("🚀 Запуск агента...")
        try:
            result = await agent.run(goal)
        except Exception as e:
            await session_logger.error(f"Ошибка при выполнении agent.run: {e}", exc_info=True)
            raise
        await session_logger.info(f"✅ Агент завершил работу")

        # Проверка на ошибку в result.error (для ExecutionResult)
        if hasattr(result, 'error') and result.error:
            await session_logger.error(f"AgentError: {result.error}")
            raise RuntimeError(f"Ошибка агента: {result.error}")

        # Проверка на ошибку в metadata
        if hasattr(result, 'metadata') and result.metadata:
            metadata = result.metadata
            logger.debug(f"DEBUG: metadata type={type(metadata)}, value={metadata}")
            if isinstance(metadata, dict):
                error_msg = metadata.get('error')
                if error_msg:
                    await session_logger.error(f"AgentError: {error_msg}")
                    raise RuntimeError(f"Ошибка агента: {error_msg}")
            elif isinstance(metadata, str):
                # Если metadata - строка, это уже сообщение об ошибке
                await session_logger.error(f"AgentError: {metadata}")
                raise RuntimeError(f"Ошибка агента: {metadata}")

        # Завершение сессии успешно
        await session_logger.end_session(success=True, result=str(result)[:500])
        logger.info(f"Сессия завершена успешно: {session_id}")

        return result

    except Exception as e:
        if session_logger:
            await session_logger.exception(f"Ошибка сессии: {e}", e)
            await session_logger.end_session(success=False, result=str(e))
        else:
            logger.error(f"Ошибка в run_agent: {e}", exc_info=True)
        raise

    finally:
        # Сначала останавливаем инфраструктуру (чтобы не было попыток публикации после остановки EventBus)
        await infrastructure_context.shutdown()
        # Затем завершаем систему логирования
        await shutdown_logging_system()
        logger.debug("Ресурсы освобождены")


def main() -> int:
    """Точка входа."""
    try:
        # Логирование настраивается автоматически в run_agent через init_logging_system()
        print(f"Анализирую вопрос: {GOAL}")

        result = asyncio.run(run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE
        ))

        logger = logging.getLogger("main")
        logger.info("\n" + "="*60)
        logger.info("✅ ОТВЕТ:")
        logger.info("="*60)

        result_text = str(result)[:500] if len(str(result)) > 500 else str(result)
        logger.info(f"✅ Результат: {result_text}")
        logger.debug(f"Полный результат: {result}")

        return 0

    except KeyboardInterrupt:
        print("\n⏸️ Прервано пользователем")
        return 0
    except Exception as e:
        logger = logging.getLogger("main")
        logger.error(f"❌ Произошла ошибка: {str(e)[:200]}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
