"""
Точка входа в систему агентов.

ВСЁ ЛОГИРОВАНИЕ ЧЕРЕЗ EventBusLogger (шину событий).
"""
import asyncio
import logging
import sys
import traceback
import warnings
from typing import Optional

from core.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig
from core.config import get_config
from core.errors.error_handler import ErrorContext, ErrorSeverity, get_error_handler
from core.infrastructure.event_bus.unified_event_bus import EventType, UnifiedEventBus
from core.infrastructure.logging.session import LoggingSession
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.utils.encoding import setup_encoding

# Вызываем ОДИН раз в начале программы
setup_encoding()

# Подавляем предупреждения Pydantic
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")

# Подавляем вывод llama.cpp (технические сообщения в stderr)
from core.utils.encoding import StderrFilter

sys.stderr = StderrFilter(sys.stderr, patterns=["llama_context:", "n_ctx_per_seq"])

# Подавляем tqdm прогресс-бары llama-cpp-python
import os
os.environ["TQDM_DISABLE"] = "1"

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

GOAL = "Какие книги написал Пушкин?"
MAX_STEPS = 5
TEMPERATURE = 0.3


async def run_agent(
    goal: str,
    max_steps: int = None,
    temperature: float = None,
    dialogue_history=None  # ← НОВОЕ: история диалога между запросами
) -> str:
    """
    Запуск агента с заданной целью.

    ВСЁ ЛОГИРОВАНИЕ ЧЕРЕЗ EventBusLogger (шину событий).
    Логирование инициализируется внутри InfrastructureContext.initialize().

    ПАРАМЕТРЫ:
    - goal: Цель агента
    - max_steps: Максимальное количество шагов
    - temperature: Температура LLM
    - dialogue_history: История диалога из предыдущих запросов (опционально)
    """
    config = get_config(profile='prod', data_dir='data')

    print("🚀 Создание инфраструктурного контекста...", flush=True)
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    session_id = str(infrastructure_context.id)

    # Простая async-обёртка для логирования
    # Логгер агента создаётся ТОЛЬКО в AgentRuntime (runtime.py:82)
    # Здесь используем app_logger для общих сообщений сессии
    class SessionLogger:
        """Async-обёртка для стандартного logging.Logger."""
        def __init__(self, logger: logging.Logger):
            self._logger = logger

        async def start_session(self, goal: str):
            self._logger.info(f"🚀 Сессия начата: {session_id}", extra={"event_type": LogEventType.AGENT_START})
            self._logger.info(f"📝 Цель: {goal}", extra={"event_type": LogEventType.USER_PROGRESS})

        async def info(self, message: str):
            self._logger.info(message, extra={"event_type": LogEventType.INFO})

        async def error(self, message: str):
            self._logger.error(message, extra={"event_type": LogEventType.ERROR})

        async def warning(self, message: str):
            self._logger.warning(message, extra={"event_type": LogEventType.WARNING})

        async def end_session(self, success: bool, result: str):
            status = "успешно" if success else "с ошибкой"
            self._logger.info(f"✅ Сессия завершена {status}: {session_id}", extra={"event_type": LogEventType.AGENT_STOP})

        async def exception(self, message: str, exc: Exception):
            self._logger.exception(f"{message}: {exc}", extra={"event_type": LogEventType.CRITICAL})

        def error_sync(self, message: str):
            self._logger.error(message, extra={"event_type": LogEventType.ERROR})

    session_logger = SessionLogger(infrastructure_context.log_session.app_logger)

    session_info = infrastructure_context.session_handler.get_session_info()

    error_handler = get_error_handler()

    try:
        await session_logger.start_session(goal=goal)
        await session_logger.info(f"🚀 Сессия начата: {session_id}")
        await session_logger.info(f"📝 Цель: {goal}")

        app_config = AppConfig.from_discovery(
            profile="prod",
            data_dir=str(getattr(infrastructure_context.config, 'data_dir', 'data')),
        )
        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        success = await application_context.initialize()

        if not success:
            await session_logger.error(f"❌ ApplicationContext.initialize() вернул False")
            await session_logger.error(f"   is_initialized = {application_context.is_initialized}")
            raise RuntimeError("ApplicationContext не удалось инициализировать")

        await session_logger.info("🚀 Запуск агента...")

        agent_factory = AgentFactory(application_context)

        agent_config_kwargs = {}
        if max_steps is not None:
            agent_config_kwargs['max_steps'] = max_steps
        if temperature is not None:
            agent_config_kwargs['temperature'] = temperature

        agent_config = AgentConfig(**agent_config_kwargs) if agent_config_kwargs else None

        agent = await agent_factory.create_agent(
            goal=goal,
            config=agent_config,
            dialogue_history=dialogue_history  # ← НОВОЕ: передаём историю
        )

        await session_logger.info("🔄 Запуск выполнения агента...")

        try:
            result = await agent.run(goal)
            await session_logger.info("✅ Выполнение агента завершено")
        except Exception as run_error:
            session_logger.error_sync(f"❌ КРИТИЧЕСКАЯ ОШИБКА при выполнении agent.run(): {run_error}")
            session_logger.error_sync(f"📋 Тип: {type(run_error).__name__}")
            session_logger.error_sync(f"📝 Traceback:\n{traceback.format_exc()}")
            raise

        if isinstance(result, str):
            await session_logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: agent.run() вернул строку вместо объекта!")
            await session_logger.error(f"📋 Значение: {result}")
            raise RuntimeError(f"agent.run() вернул строку вместо ExecutionResult: {result}")

        if hasattr(result, 'error') and result.error:
            if isinstance(result.error, str):
                await session_logger.error(f"⚠️ result.error это строка (не Exception): {result.error}")
                await session_logger.error(f"📋 Это может быть причиной проблемы 'str object has no attribute get'")

            error_details = {
                "error": result.error,
                "error_type": type(result.error).__name__ if hasattr(result.error, '__class__') else type(result.error),
                "result_type": type(result).__name__,
            }

            if hasattr(result, 'metadata'):
                metadata = getattr(result, 'metadata', None)
                if metadata is not None and not isinstance(metadata, dict):
                    await session_logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: result.metadata это не dict (тип: {type(metadata).__name__})")
                    await session_logger.error(f"📋 Значение: {metadata}")
                    error_details["metadata_type"] = type(metadata).__name__
                    error_details["metadata_value"] = str(metadata)
                elif isinstance(metadata, dict):
                    error_details["metadata"] = metadata
                    if 'error' in metadata:
                        meta_error = metadata.get('error')
                        if isinstance(meta_error, str):
                            await session_logger.error(f"⚠️ metadata['error'] это строка: {meta_error}")

            if isinstance(result.error, dict):
                error_details["error_dict"] = result.error
            elif hasattr(result, 'state'):
                error_details["state"] = getattr(result, 'state', None)

            import traceback
            error_details["traceback"] = traceback.format_exc()

            error_context = ErrorContext(
                component="AgentRuntime",
                operation="run",
                session_id=session_id,
                metadata={
                    "goal": goal,
                    "error_details": error_details,
                }
            )
            await error_handler.handle(
                RuntimeError(f"{result.error} (type: {type(result.error).__name__})"),
                context=error_context,
                severity=ErrorSeverity.HIGH
            )
            await session_logger.error(f"❌ Ошибка агента: {result.error}")
            await session_logger.error(f"📋 Детали ошибки: {error_details}")
            raise RuntimeError(f"Ошибка агента: {result.error} (тип: {type(result.error).__name__}, файл: main.py, строка: 176)")

        if hasattr(result, 'metadata') and result.metadata:
            metadata = result.metadata
            if isinstance(metadata, dict):
                error_msg = metadata.get('error')
                if error_msg:
                    error_details = {
                        "error_msg": error_msg,
                        "metadata": metadata,
                        "result_type": type(result).__name__,
                    }

                    import traceback
                    error_details["traceback"] = traceback.format_exc()

                    error_context = ErrorContext(
                        component="AgentRuntime",
                        operation="run",
                        session_id=session_id,
                        metadata={
                            "goal": goal,
                            "error_details": error_details,
                        }
                    )
                    await error_handler.handle(
                        RuntimeError(f"{error_msg} (из metadata)"),
                        context=error_context,
                        severity=ErrorSeverity.HIGH
                    )
                    await session_logger.error(f"❌ Ошибка в metadata: {error_msg}")
                    await session_logger.error(f"📋 Детали metadata: {metadata}")
                    raise RuntimeError(f"Ошибка агента: {error_msg} (из metadata, файл: main.py, строка: 200)")

        result_preview = str(result)
        await session_logger.end_session(success=True, result=result_preview)
        await session_logger.info(f"✅ Сессия завершена успешно: {session_id}")
        await session_logger.info(f"📊 Результат:")

        RESET = "\033[0m"
        BOLD = "\033[1m"
        CYAN = "\033[36m"
        YELLOW = "\033[33m"

        print(f"\n{CYAN}{'═'*60}{RESET}")
        print(f"{BOLD}{YELLOW}📖 ОТВЕТ:{RESET}")
        print(f"{CYAN}{'─'*60}{RESET}")
        print(f"{BOLD}{result_preview}{RESET}")
        print(f"{CYAN}{'═'*60}{RESET}\n")

        return result

    except Exception as e:
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

        RESET = "\033[0m"
        RED = "\033[31m"
        BOLD = "\033[1m"
        print(f"\n{RED}{BOLD}❌ ОШИБКА: {e}{RESET}\n")
        raise

    finally:
        if infrastructure_context and hasattr(infrastructure_context, 'session_handler'):
            await infrastructure_context.session_handler.shutdown()

        if 'application_context' in locals():
            await application_context.shutdown()

        await infrastructure_context.shutdown()

        # Корректно закрываем все файловые хендлеры
        infrastructure_context.log_session.shutdown()


async def main_async(dialogue_history=None) -> tuple:
    """Точка входа (async версия).
    
    ВОЗВРАЩАЕТ:
    - tuple: (exit_code, dialogue_history)
    """
    try:
        result = await run_agent(
            goal=GOAL,
            max_steps=MAX_STEPS,
            temperature=TEMPERATURE,
            dialogue_history=dialogue_history  # ← НОВОЕ: передаём историю
        )

        event_bus = get_event_bus_from_result(result)
        if event_bus:
            await event_bus.publish(
                EventType.USER_RESULT,
                data={"message": "ОТВЕТ АГЕНТА", "icon": "📋"},
                session_id="system",
            )

            if hasattr(result, 'data') and result.data:
                from pydantic import BaseModel
                if isinstance(result.data, BaseModel):
                    final_answer = result.data.final_answer
                    if final_answer:
                        await event_bus.publish(
                            EventType.USER_RESULT,
                            data={"message": final_answer},
                            session_id="system",
                        )
                    else:
                        summary = result.data.summary_of_steps
                        await event_bus.publish(
                            EventType.USER_RESULT,
                            data={"message": summary or str(result.data)},
                            session_id="system",
                        )
                elif isinstance(result.data, dict):
                    final_answer = result.data.get('final_answer', '')
                    if final_answer:
                        await event_bus.publish(
                            EventType.USER_RESULT,
                            data={"message": final_answer},
                            session_id="system",
                        )
                    else:
                        summary = result.data.get('summary', str(result.data))
                        await event_bus.publish(
                            EventType.USER_RESULT,
                            data={"message": summary},
                            session_id="system",
                        )
                else:
                    await event_bus.publish(
                        EventType.USER_RESULT,
                        data={"message": str(result.data)},
                        session_id="system",
                    )
            else:
                await event_bus.publish(
                    EventType.USER_RESULT,
                    data={"message": str(result)},
                    session_id="system",
                )

            if hasattr(result, 'metadata') and result.metadata:
                from pydantic import BaseModel
                if isinstance(result.data, BaseModel):
                    data_dict = result.data.model_dump()
                    steps = result.data.metadata.total_steps if hasattr(result.data, 'metadata') else 'N/A'
                else:
                    data_dict = result.data if isinstance(result.data, dict) else {}
                    steps = result.metadata.get('total_steps') or \
                            result.metadata.get('steps_count') or \
                            (data_dict.get('metadata', {}).get('total_steps') if data_dict else None) or \
                            'N/A'
                errors = result.metadata.get('error_count', 0)
                await event_bus.publish(
                    EventType.USER_RESULT,
                    data={"message": f"Шагов выполнено: {steps}, Ошибок: {errors}"},
                    session_id="system",
                )

        return 0

    except KeyboardInterrupt:
        return 0
    except Exception as e:
        error_handler = get_error_handler()
        error_context = ErrorContext(
            component="main",
            operation="main",
            metadata={"goal": GOAL}
        )
        await error_handler.handle(
            e,
            context=error_context,
            severity=ErrorSeverity.CRITICAL
        )

        return 1


def get_event_bus_from_result(result) -> Optional['UnifiedEventBus']:
    """Получение event_bus из результата."""
    try:
        if hasattr(result, 'application_context') and result.application_context:
            app_ctx = result.application_context
            if hasattr(app_ctx, 'infrastructure_context') and app_ctx.infrastructure_context:
                return app_ctx.infrastructure_context.event_bus
    except Exception:
        pass
    return None


def main() -> int:
    """Точка входа (синхронная обёртка)."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
