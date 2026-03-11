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


# === ВОПРОС ДЛЯ ТЕСТИРОВАНИЯ ===
# GOAL = "Какие книги написал Пушкин?"
GOAL = "Где проходит действие в произведении Капитанская дочка?"
MAX_STEPS = 10
TEMPERATURE = 0.2


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
    print("🚀 Создание инфраструктурного контекста...", flush=True)
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    print("✅ Инфраструктурный контекст инициализирован", flush=True)

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
        session_logger.start_session(goal=goal)
        session_logger.info(f"🚀 Сессия начата: {session_id}")
        session_logger.info(f"📝 Цель: {goal}")

        # Создание прикладного контекста
        # ✅ ИСПОЛЬЗУЕМ ОБЩИЙ ResourceDiscovery из infrastructure_context
        app_config = AppConfig.from_discovery(
            profile="prod",
            data_dir=str(getattr(infrastructure_context.config, 'data_dir', 'data')),
            discovery=infrastructure_context.resource_discovery  # ← Используем напрямую (не deprecated)
        )
        application_context = ApplicationContext(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile="prod"
        )

        # ✅ СИНХРОННАЯ ИНИЦИАЛИЗАЦИЯ
        success = application_context.initialize_sync()
        
        if not success:
            print(f"❌ ApplicationContext.initialize_sync() вернул False")
            print(f"   _state = {application_context._state}")
            print(f"   _initialized = {application_context._initialized}")
            raise RuntimeError("ApplicationContext не удалось инициализировать")

        # ✅ ЯВНАЯ ПРОВЕРКА: все контексты инициализированы
        print("✅ InfrastructureContext инициализирован")
        print("✅ ApplicationContext инициализирован")
        print("🚀 Запуск агента...")

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
        agent = agent_factory.create_agent_sync(goal=goal, config=agent_config)

        session_logger.info("🚀 Запуск выполнения агента...")
        
        # === ДИАГНОСТИКА: Проверяем result перед использованием ===
        import sys
        import traceback
        
        # Синхронный вывод для критических сообщений
        try:
            # Принудительная синхронная печать для последовательности
            print("🔄 Запуск выполнения агента...", flush=True)
            session_logger.info_sync("🔄 Запуск выполнения агента...")
            result = agent._run_sync(goal)
            print("✅ Выполнение агента завершено", flush=True)
            session_logger.info_sync("✅ Выполнение агента завершено")
        except Exception as run_error:
            # Ошибка во время выполнения agent.run()
            print("❌ КРИТИЧЕСКАЯ ОШИБКА при выполнении agent.run()", flush=True)
            session_logger.error_sync(f"❌ КРИТИЧЕСКАЯ ОШИБКА при выполнении agent.run(): {run_error}")
            session_logger.error_sync(f"📋 Тип: {type(run_error).__name__}")
            session_logger.error_sync(f"📝 Traceback:\n{traceback.format_exc()}")
            raise
        
        # Добавим синхронный вывод для завершения
        print("🚀 Агент успешно завершён", flush=True)
        
        # Проверяем что result это не строка
        if isinstance(result, str):
            session_logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: agent.run() вернул строку вместо объекта!")
            session_logger.error(f"📋 Значение: {result[:500] if len(result) > 500 else result}")
            raise RuntimeError(f"agent.run() вернул строку вместо ExecutionResult: {result}")
        
        # Проверка на ошибку в result.error (для ExecutionResult)
        if hasattr(result, 'error') and result.error:
            # Проверяем что error это не строка (должна быть None или Exception)
            if isinstance(result.error, str):
                session_logger.error(f"⚠️ result.error это строка (не Exception): {result.error}")
                session_logger.error(f"📋 Это может быть причиной проблемы 'str object has no attribute get'")
            
            # Детальная информация об ошибке
            error_details = {
                "error": result.error,
                "error_type": type(result.error).__name__ if hasattr(result.error, '__class__') else type(result.error),
                "result_type": type(result).__name__,
            }
            
            # Проверяем metadata - это dict?
            if hasattr(result, 'metadata'):
                metadata = getattr(result, 'metadata', None)
                if metadata is not None and not isinstance(metadata, dict):
                    session_logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: result.metadata это не dict (тип: {type(metadata).__name__})")
                    session_logger.error(f"📋 Значение: {metadata}")
                    error_details["metadata_type"] = type(metadata).__name__
                    error_details["metadata_value"] = str(metadata)
                elif isinstance(metadata, dict):
                    error_details["metadata"] = metadata
                    # Проверяем есть ли в metadata ошибка
                    if 'error' in metadata:
                        meta_error = metadata.get('error')
                        if isinstance(meta_error, str):
                            session_logger.error(f"⚠️ metadata['error'] это строка: {meta_error}")
            
            # Если error это dict, добавим детали
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
            error_handler.handle(
                RuntimeError(f"{result.error} (type: {type(result.error).__name__})"),
                context=error_context,
                severity=ErrorSeverity.HIGH
            )
            session_logger.error(f"❌ Ошибка агента: {result.error}")
            session_logger.error(f"📋 Детали ошибки: {error_details}")
            raise RuntimeError(f"Ошибка агента: {result.error} (тип: {type(result.error).__name__}, файл: main.py, строка: 176)")

        # Проверка на ошибку в metadata
        if hasattr(result, 'metadata') and result.metadata:
            metadata = result.metadata
            if isinstance(metadata, dict):
                error_msg = metadata.get('error')
                if error_msg:
                    # Детальная информация об ошибке
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
                    error_handler.handle(
                        RuntimeError(f"{error_msg} (из metadata)"),
                        context=error_context,
                        severity=ErrorSeverity.HIGH
                    )
                    session_logger.error(f"❌ Ошибка в metadata: {error_msg}")
                    session_logger.error(f"📋 Детали metadata: {metadata}")
                    raise RuntimeError(f"Ошибка агента: {error_msg} (из metadata, файл: main.py, строка: 200)")

        # Завершение сессии успешно
        result_preview = str(result)[:500] if len(str(result)) > 500 else str(result)
        session_logger.end_session(success=True, result=result_preview)
        session_logger.info(f"✅ Сессия завершена успешно: {session_id}")
        session_logger.info(f"📊 Результат: {result_preview}")

        return result

    except Exception as e:
        # Обработка ошибки через ErrorHandler
        error_context = ErrorContext(
            component="main.run_agent",
            operation="run_agent",
            session_id=session_id,
            metadata={"goal": goal}
        )
        error_handler.handle(
            e,
            context=error_context,
            severity=ErrorSeverity.CRITICAL
        )
        
        session_logger.exception(f"❌ Ошибка сессии: {e}", e)
        session_logger.end_session(success=False, result=str(e))
        raise

    finally:
        # Завершение обработчика логов сессии
        if session_log_handler:
            session_log_handler.shutdown()

        # Завершение прикладного контекста (включая LLMOrchestrator)
        if 'application_context' in locals():
            application_context.shutdown()

        # Остановка инфраструктуры
        infrastructure_context.shutdown()

        # Завершение системы логирования
        shutdown_logging_system()


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
        
        # Проверяем тип результата
        if hasattr(result, 'data') and result.data:
            # ExecutionResult — извлекаем данные
            if isinstance(result.data, dict):
                final_answer = result.data.get('final_answer', '')
                if final_answer:
                    print(f"\n{final_answer}")
                else:
                    # Если final_answer нет, выводим summary
                    summary = result.data.get('summary', str(result.data))
                    print(f"\n{summary}")
            else:
                print(f"\n{result.data}")
        else:
            print(f"\n{result}")
        
        # Дополнительная информация
        if hasattr(result, 'metadata'):
            print("\n" + "-" * 60)
            print("📊 Метаданные:")
            if result.metadata:
                steps = result.metadata.get('steps_executed', 'N/A')
                errors = result.metadata.get('error_count', 0)
                print(f"  - Шагов выполнено: {steps}")
                print(f"  - Ошибок: {errors}")
        
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
