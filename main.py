"""
Точка входа для запуска агента.

Использует архитектуру проекта:
- InfrastructureContext для инфраструктуры
- ApplicationContext для прикладной логики
- ErrorHandler для обработки ошибок
- EventBusLogger для логирования через шину событий
"""
import asyncio
import sys
import warnings
import os
import io

# Устанавливаем UTF-8 кодировку для консоли Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')  # Устанавливаем UTF-8 кодировку
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Подавляем предупреждения Pydantic
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

# Подавляем вывод llama.cpp (сообщения о контексте) через перенаправление stderr
class StderrFilter:
    """Фильтр stderr для подавления технических сообщений."""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.buffer = io.StringIO()
    
    def write(self, text):
        # Пропускаем сообщения llama.cpp о контексте
        if "llama_context:" in text and "n_ctx_per_seq" in text:
            return
        self.original_stderr.write(text)
        self.original_stderr.flush()
    
    def flush(self):
        self.original_stderr.flush()
    
    def isatty(self):
        return self.original_stderr.isatty()

# Устанавливаем фильтр stderr
sys.stderr = StderrFilter(sys.stderr)

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig
from core.errors import get_error_handler, ErrorContext, ErrorSeverity
from core.infrastructure.logging import (
    shutdown_logging_system,
    get_session_logger,
    create_session_log_handler,
)
from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber


# === ВОПРОС ДЛЯ ТЕСТИРОВАНИЯ ===
GOAL = "Какие книги написал Пушкин?"
MAX_STEPS = 10
TEMPERATURE = 0.7


async def run_agent(goal: str, max_steps: int = None, temperature: float = None) -> str:
    """
    Запуск агента с заданной целью.

    ВСЁ ЛОГИРОВАНИЕ ЧЕРЕЗ EventBusLogger (шину событий).
    Логирование инициализируется внутри InfrastructureContext.initialize().
    """
    # Загрузка конфигурации приложения
    config = get_config(profile='dev')

    # Создание и инициализация инфраструктурного контекста
    # (логирование инициализируется внутри)
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    # Получаем session_id и создаём логгер сессии
    session_id = str(infrastructure_context.id)
    session_logger = get_session_logger(session_id, agent_id="agent_001")

    # Создаём новый обработчик логов сессии (с датой/временем в имени папки)
    # session_id=None чтобы получать события из ВСЕХ сессий (включая "system")
    session_log_handler = create_session_log_handler(
        event_bus=infrastructure_context.event_bus,
        session_id=None,  # Получать события из всех сессий
        agent_id="agent_001"
    )
    session_info = session_log_handler.get_session_info()

    # Получаем глобальный обработчик ошибок
    error_handler = get_error_handler()

    try:
        # Начало сессии
        await session_logger.start_session(goal=goal)
        await session_logger.info(f"🚀 Сессия начата: {session_id}")
        await session_logger.info(f"📝 Цель: {goal}")

        # Создание прикладного контекста
        # ✅ ИСПОЛЬЗУЕМ ОБЩИЙ ResourceDiscovery из infrastructure_context
        app_config = AppConfig.from_discovery(
            profile="prod",
            data_dir=str(getattr(infrastructure_context.config, 'data_dir', 'data')),
            discovery=infrastructure_context.get_resource_discovery()  # ← Передаём общий экземпляр
        )
        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        await application_context.initialize()

        # Подписка на события LLM через LLMEventSubscriber
        llm_subscriber = LLMEventSubscriber(
            event_bus=infrastructure_context.event_bus,
            log_full_content=True
        )
        llm_subscriber.subscribe(infrastructure_context.event_bus)

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

        await session_logger.info("🚀 Запуск выполнения агента...")
        result = await agent.run(goal)

        # Проверка на ошибку в result.error (для ExecutionResult)
        if hasattr(result, 'error') and result.error:
            error_context = ErrorContext(
                component="AgentRuntime",
                operation="run",
                session_id=session_id,
                metadata={"goal": goal}
            )
            await error_handler.handle(
                RuntimeError(result.error),
                context=error_context,
                severity=ErrorSeverity.HIGH
            )
            await session_logger.error(f"❌ Ошибка агента: {result.error}")
            raise RuntimeError(f"Ошибка агента: {result.error}")

        # Проверка на ошибку в metadata
        if hasattr(result, 'metadata') and result.metadata:
            metadata = result.metadata
            if isinstance(metadata, dict):
                error_msg = metadata.get('error')
                if error_msg:
                    error_context = ErrorContext(
                        component="AgentRuntime",
                        operation="run",
                        session_id=session_id,
                        metadata={"goal": goal}
                    )
                    await error_handler.handle(
                        RuntimeError(error_msg),
                        context=error_context,
                        severity=ErrorSeverity.HIGH
                    )
                    await session_logger.error(f"❌ Ошибка в metadata: {error_msg}")
                    raise RuntimeError(f"Ошибка агента: {error_msg}")

        # Завершение сессии успешно
        result_preview = str(result)[:500] if len(str(result)) > 500 else str(result)
        await session_logger.end_session(success=True, result=result_preview)
        await session_logger.info(f"✅ Сессия завершена успешно: {session_id}")
        await session_logger.info(f"📊 Результат: {result_preview}")

        return result

    except Exception as e:
        # Обработка ошибки через ErrorHandler
        error_context = ErrorContext(
            component="main.run_agent",
            operation="run_agent",
            session_id=session_id,
            metadata={"goal": goal}
        )
        await error_handler.handle(
            e,
            context=error_context,
            severity=ErrorSeverity.CRITICAL
        )
        
        await session_logger.exception(f"❌ Ошибка сессии: {e}", e)
        await session_logger.end_session(success=False, result=str(e))
        raise

    finally:
        # Завершение обработчика логов сессии
        if session_log_handler:
            await session_log_handler.shutdown()
        
        # Остановка инфраструктуры
        await infrastructure_context.shutdown()
        
        # Завершение системы логирования
        await shutdown_logging_system()


def main() -> int:
    """Точка входа."""
    try:
        result = asyncio.run(run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE
        ))

        # Вывод результата
        print("\n" + "=" * 60)
        print("📋 ОТВЕТ АГЕНТА:")
        print("=" * 60)
        print(result)
        print("=" * 60)

        return 0

    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        return 0
    except Exception as e:
        # Обработка ошибки через ErrorHandler
        error_handler = get_error_handler()
        error_context = ErrorContext(
            component="main",
            operation="main",
            metadata={"goal": GOAL}
        )
        asyncio.run(error_handler.handle(
            e,
            context=error_context,
            severity=ErrorSeverity.CRITICAL
        ))

        print(f"\n❌ Произошла ошибка: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
