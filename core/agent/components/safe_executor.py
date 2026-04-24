"""
Безопасный исполнитель действий с network retry.

АРХИТЕКТУРА (Этап 2):
- Обёртка над ActionExecutor для network retry
- ТОЛЬКО retry для TRANSIENT ошибок (timeout, connection)
- НЕ принимает решений о switch/abort/fail
- Запись ошибок в FailureMemory для Pattern

ОТВЕТСТВЕННОСТЬ:
- Выполнение действий через ActionExecutor
- Retry для временных ошибок (TRANSIENT)
- Запись в FailureMemory

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
safe_executor = SafeExecutor(
    executor=action_executor,
    failure_memory=FailureMemory(),
    max_retries=3
)

# Pattern сам читает failures и решает что делать
result = await safe_executor.execute(...)
"""
import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.infrastructure.logging.session import LoggingSession

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ErrorCategory, ErrorType
from core.models.types.retry_policy import ExecutionErrorInfo, RetryResult, RetryDecision
from core.errors.error_classifier import ErrorClassifier
from core.errors.failure_memory import FailureMemory
from core.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.policy import RetryPolicy
from core.infrastructure.event_bus.unified_event_bus import EventType


class SafeExecutor:
    """
    Безопасный исполнитель действий с обработкой ошибок.
    
    ПРИНЦИПЫ:
    - Изоляция ошибок от основного потока выполнения
    - Классификация ошибок для правильных решений
    - Экспоненциальная задержка для retry
    - Запись в FailureMemory для анализа паттернов
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    safe_executor = SafeExecutor(
        executor=action_executor,
        failure_memory=FailureMemory()
    )
    
    result = await safe_executor.execute(
        capability_name="search.database",
        parameters={"query": "test"},
        context=context
    )
    
    if result.status == ExecutionStatus.FAILED:
        # Проверка рекомендации
        recommendation = result.metadata.get("recommendation")
        if recommendation == "switch_pattern":
            # Переключить паттерн
            pass
    """
    
    def __init__(
        self,
        executor: ActionExecutor,
        failure_memory: FailureMemory,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        jitter: bool = True,
        log_session: Optional['LoggingSession'] = None
    ):
        """
        Инициализация безопасного исполнителя.

        ПАРАМЕТРЫ:
        - executor: ActionExecutor для выполнения действий
        - failure_memory: FailureMemory для записи ошибок
        - max_retries: максимальное количество попыток
        - base_delay: базовая задержка (сек) для экспоненциального увеличения
        - max_delay: максимальная задержка (сек)
        - jitter: применять ли случайное изменение задержки
        - log_session: сессия логирования
        """
        self.executor = executor
        self.failure_memory = failure_memory
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.error_classifier = ErrorClassifier()
        self._log_session = log_session

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.app_logger:
            return self._log_session.app_logger
        return logging.getLogger(__name__)
    
    async def execute(
        self,
        capability_name: str,
        parameters: dict,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнить действие с network retry.

        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - parameters: параметры
        - context: контекст

        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения

        АЛГОРИТМ (Этап 2):
        1. Попытка выполнения через executor
        2. При TRANSIENT ошибке — retry с задержкой
        3. При других ошибках — запись в FailureMemory и возврат failure
        4. Pattern сам читает failures и принимает решения
        """
        self._get_logger().debug(
            f"SafeExecutor.execute: {capability_name}",
            extra={"event_type": EventType.DEBUG}
        )

        last_error: Optional[Exception] = None
        retry_count = 0

        for attempt in range(self.max_retries):
            try:
                # Попытка выполнения
                result = await self.executor.execute_action(
                    action_name=capability_name,
                    parameters=parameters,
                    context=context
                )

                # Успех — сброс failure memory
                self.failure_memory.reset(capability_name)

                # Добавляем информацию о retry в metadata
                if retry_count > 0:
                    result.metadata["retry_count"] = retry_count

                return result

            except Exception as e:
                last_error = e
                retry_count = attempt + 1

                # Классификация ошибки
                error_type, _ = self.error_classifier.classify(e, capability_name)

                # Запись в FailureMemory
                self.failure_memory.record(
                    capability=capability_name,
                    error_type=error_type,
                    timestamp=datetime.now()
                )

                self._get_logger().warning(
                    f"Ошибка {error_type.value}: {capability_name} (attempt {attempt + 1}/{self.max_retries}): {e}",
                    extra={"event_type": EventType.WARNING},
                    exc_info=True
                )

                # Retry ТОЛЬКО для TRANSIENT ошибок, КРОМЕ final_answer
                if error_type == ErrorType.TRANSIENT and capability_name != "final_answer.generate":
                    if attempt < self.max_retries - 1:
                        delay = self._calculate_delay(attempt)
                        await asyncio.sleep(delay)
                        continue  # Следующая попытка
                
                # Для всех остальных ошибок — возврат failure
                # Pattern сам прочитает failures и решит что делать
                return self._create_failure_result(
                    capability_name=capability_name,
                    error=e,
                    error_type=error_type,
                    retry_count=retry_count
                )

        # Достижение сюда означает что все retry исчерпаны
        return self._create_failure_result(
            capability_name=capability_name,
            error=last_error or Exception("Unknown error"),
            error_type=ErrorType.TRANSIENT,
            retry_count=retry_count
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Рассчитать задержку перед retry.
        
        ПАРАМЕТРЫ:
        - attempt: номер попытки (0-based)
        
        ВОЗВРАЩАЕТ:
        - float: задержка в секундах
        
        ФОРМУЛА:
        delay = min(base_delay * (2 ^ attempt), max_delay) + jitter
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        if self.jitter:
            # Добавляем случайный jitter от 50% до 150%
            delay *= random.uniform(0.5, 1.5)
        
        return delay
    
    def _create_failure_result(
        self,
        capability_name: str,
        error: Exception,
        error_type: ErrorType,
        retry_count: int
    ) -> ExecutionResult:
        """
        Создать результат неудачного выполнения.

        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - error: исключение
        - error_type: тип ошибки
        - retry_count: количество попыток

        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат с metadata

        ⚠️ БЕЗ decision logic: Pattern сам решает что делать
        """
        # Маппинг ErrorType → ErrorCategory для совместимости
        error_category_map = {
            ErrorType.TRANSIENT: ErrorCategory.TRANSIENT,
            ErrorType.LOGIC: ErrorCategory.UNKNOWN,
            ErrorType.VALIDATION: ErrorCategory.INVALID_INPUT,
            ErrorType.FATAL: ErrorCategory.FATAL
        }

        error_category = error_category_map.get(error_type, ErrorCategory.UNKNOWN)

        # Получаем количество ошибок из FailureMemory
        failure_count = self.failure_memory.get_count(capability_name)

        metadata = {
            "error_type": error_type.value,
            "failure_count": failure_count,
            "retry_count": retry_count
            # ⚠️ БЕЗ recommendation — Pattern сам решает
            # ⚠️ БЕЗ should_switch_pattern — Pattern сам анализирует failures
        }

        return ExecutionResult.failure(
            error=str(error),
            metadata=metadata,
            error_category=error_category
        )

    def get_failure_memory(self) -> FailureMemory:
        """
        Получить FailureMemory для внешней проверки.
        
        ВОЗВРАЩАЕТ:
        - FailureMemory: экземпляр памяти ошибок
        """
        return self.failure_memory
