"""
Безопасный исполнитель действий с обработкой ошибок.

АРХИТЕКТУРА:
- Обёртка над ActionExecutor для обработки ошибок
- Классификация ошибок через ErrorClassifier
- Запись ошибок в FailureMemory
- Принятие решений о retry/switch/abort/fail
- Экспоненциальная задержка с jitter для retry

ОТВЕТСТВЕННОСТЬ:
- Выполнение действий через ActionExecutor
- Обработка исключений и классификация ошибок
- Retry logic для TRANSIENT ошибок
- Запись в FailureMemory для принятия решений о паттернах

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
safe_executor = SafeExecutor(
    executor=action_executor,
    failure_memory=FailureMemory(),
    max_retries=3,
    base_delay=0.5
)

result = await safe_executor.execute(
    capability_name="search.database",
    parameters={"query": "test"},
    context=execution_context
)
"""
import asyncio
import random
from datetime import datetime
from typing import Optional, Any

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ErrorCategory, ErrorType
from core.models.types.retry_policy import ExecutionErrorInfo, RetryResult, RetryDecision
from core.application.agent.components.error_classifier import ErrorClassifier
from core.application.agent.components.failure_memory import FailureMemory
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.application.agent.components.policy import AgentPolicy


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
        jitter: bool = True
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
        """
        self.executor = executor
        self.failure_memory = failure_memory
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.error_classifier = ErrorClassifier()
        
        # ← НОВОЕ: Логирование через executor.event_bus_logger
        self._event_bus_logger = getattr(executor, '_event_bus_logger', None)
    
    async def execute(
        self,
        capability_name: str,
        parameters: dict,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнить действие с обработкой ошибок.
        
        ПАРАМЕТРЫ:
        - capability_name: имя capability для выполнения
        - parameters: параметры выполнения
        - context: контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        
        АЛГОРИТМ:
        1. Попытка выполнения через executor
        2. При ошибке — классификация типа ошибки
        3. Запись в FailureMemory
        4. Принятие решения (retry/switch/abort/fail)
        5. Для TRANSIENT — retry с экспоненциальной задержкой
        6. Для остальных — возврат с рекомендацией
        """
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
                error_type, recommendation = self.error_classifier.classify(e, capability_name)

                # ← НОВОЕ: Логирование ошибки
                await self._log_error(capability_name, e, error_type, attempt)

                # Запись в FailureMemory (ЕДИНЫЙ источник!)
                self.failure_memory.record(
                    capability=capability_name,
                    error_type=error_type,
                    timestamp=datetime.now()
                )
                
                # Принятие решения на основе типа ошибки
                if error_type == ErrorType.TRANSIENT:
                    # Временная ошибка — retry с задержкой
                    if attempt < self.max_retries - 1:
                        delay = self._calculate_delay(attempt)
                        await asyncio.sleep(delay)
                        continue  # Следующая попытка
                    else:
                        # Лимит retry исчерпан
                        return self._create_failure_result(
                            capability_name=capability_name,
                            error=e,
                            error_type=error_type,
                            recommendation="max_retries_exceeded",
                            retry_count=retry_count
                        )
                
                elif error_type == ErrorType.LOGIC:
                    # Логическая ошибка — switch pattern
                    return self._create_failure_result(
                        capability_name=capability_name,
                        error=e,
                        error_type=error_type,
                        recommendation=recommendation,
                        retry_count=retry_count
                    )
                
                elif error_type == ErrorType.VALIDATION:
                    # Ошибка валидации — abort
                    return self._create_failure_result(
                        capability_name=capability_name,
                        error=e,
                        error_type=error_type,
                        recommendation=recommendation,
                        retry_count=retry_count
                    )
                
                elif error_type == ErrorType.FATAL:
                    # Критическая ошибка — fail immediately
                    return self._create_failure_result(
                        capability_name=capability_name,
                        error=e,
                        error_type=error_type,
                        recommendation=recommendation,
                        retry_count=retry_count
                    )
        
        # Достижение сюда означает что все retry исчерпаны
        return self._create_failure_result(
            capability_name=capability_name,
            error=last_error or Exception("Unknown error"),
            error_type=ErrorType.TRANSIENT,
            recommendation="max_retries_exceeded",
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
        recommendation: str,
        retry_count: int
    ) -> ExecutionResult:
        """
        Создать результат неудачного выполнения.
        
        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - error: исключение
        - error_type: тип ошибки
        - recommendation: рекомендация по обработке
        - retry_count: количество попыток
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат с metadata
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
        
        # Проверяем необходимость переключения паттерна
        should_switch = self.failure_memory.should_switch_pattern(capability_name)
        
        metadata = {
            "error_type": error_type.value,
            "recommendation": recommendation,
            "failure_count": failure_count,
            "retry_count": retry_count,
            "should_switch_pattern": should_switch
        }
        
        # Добавляем рекомендацию из FailureMemory если есть
        fm_recommendation = self.failure_memory.get_recommendation(capability_name)
        if fm_recommendation and fm_recommendation != recommendation:
            metadata["failure_memory_recommendation"] = fm_recommendation
        
        return ExecutionResult.failure(
            error=str(error),
            metadata=metadata,
            error_category=error_category
        )
    
    async def _log_error(
        self,
        capability_name: str,
        error: Exception,
        error_type: ErrorType,
        attempt: int
    ):
        """
        ← НОВОЕ: Логирование ошибки.
        
        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - error: исключение
        - error_type: тип ошибки
        - attempt: номер попытки
        """
        if self._event_bus_logger:
            log_message = (
                f"Ошибка выполнения {capability_name}: {type(error).__name__}: {str(error)[:100]} | "
                f"Тип: {error_type.value} | Попытка: {attempt + 1}/{self.max_retries}"
            )
            
            # Логирование по уровню серьезности
            if error_type == ErrorType.FATAL:
                await self._event_bus_logger.error(log_message)
            elif error_type == ErrorType.VALIDATION:
                await self._event_bus_logger.warning(log_message)
            else:
                await self._event_bus_logger.info(log_message)
    
    def get_failure_memory(self) -> FailureMemory:
        """
        Получить FailureMemory для внешней проверки.
        
        ВОЗВРАЩАЕТ:
        - FailureMemory: экземпляр памяти ошибок
        """
        return self.failure_memory
