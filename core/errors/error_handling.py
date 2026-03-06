"""
Централизованная обработка ошибок с RetryPolicy.

АРХИТЕКТУРА:
1. ErrorCategory — классификация ошибок
2. RetryPolicy — стратегия повторных попыток
3. ErrorHandler — централизованная обработка
4. Custom Exceptions — кастомные исключения

USAGE:
```python
from core.errors.error_handling import (
    ErrorHandler,
    RetryPolicy,
    ErrorCategory,
    ErrorInfo,
)

# Обработка с retry
error_handler = ErrorHandler()
retry_policy = RetryPolicy(max_retries=3)

try:
    result = await risky_operation()
except Exception as e:
    error_info = await error_handler.classify(e)
    if retry_policy.should_retry(error_info, attempt):
        delay = retry_policy.get_delay(attempt)
        await asyncio.sleep(delay)
```
"""
import asyncio
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# ============================================================
# Error Category & Severity
# ============================================================

class ErrorCategory(Enum):
    """
    Категория ошибки — определяет стратегию обработки.
    
    КАТЕГОРИИ:
    - TRANSIENT: Временная ошибка (таймаут, сеть) → retry
    - INVALID_INPUT: Ошибка валидации → abort
    - FATAL: Критическая ошибка → fail immediately
    - NOT_FOUND: Ресурс не найден → handle gracefully
    - CONFLICT: Конфликт → retry с backoff
    """
    
    TRANSIENT = "transient"           # Временная, можно retry
    INVALID_INPUT = "invalid_input"   # Ошибка ввода, retry бесполезен
    FATAL = "fatal"                   # Критическая, retry бесполезен
    NOT_FOUND = "not_found"           # Ресурс не найден
    CONFLICT = "conflict"             # Конфликт, можно retry
    UNKNOWN = "unknown"               # Неизвестная ошибка


class ErrorSeverity(Enum):
    """
    Серьезность ошибки.
    
    УРОВНИ:
    - LOW: Не влияет на работу
    - MEDIUM: Влияет на часть функциональности
    - HIGH: Критическая ошибка компонента
    - CRITICAL: Критическая ошибка системы
    """
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """
    Информация об ошибке.
    
    ATTRIBUTES:
    - error: Исключение
    - category: Категория ошибки
    - severity: Серьезность
    - component: Компонент где произошла ошибка
    - operation: Операция которая выполнялась
    - metadata: Дополнительные метаданные
    - timestamp: Время возникновения
    """
    
    error: Exception
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    component: str = "unknown"
    operation: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def error_message(self) -> str:
        """Текст ошибки."""
        return str(self.error)
    
    @property
    def error_type(self) -> str:
        """Тип исключения."""
        return type(self.error).__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "operation": self.operation,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# Retry Policy
# ============================================================

@dataclass
class RetryPolicy:
    """
    Политика повторных попыток.
    
    СТРАТЕГИЯ:
    - Экспоненциальная задержка: delay = base_delay * (2 ^ attempt)
    - Джиттер: случайная добавка для предотвращения thundering herd
    - Максимальная задержка: cap для предотвращения слишком долгих ожиданий
    
    USAGE:
    ```python
    policy = RetryPolicy(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        jitter=0.5
    )
    
    for attempt in range(policy.max_retries):
        try:
            return await operation()
        except Exception as e:
            if not policy.should_retry(e, attempt):
                raise
            await asyncio.sleep(policy.get_delay(attempt))
    ```
    """
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.5
    exponential_base: float = 2.0
    
    # Категории которые можно retry
    retryable_categories: List[ErrorCategory] = field(
        default_factory=lambda: [
            ErrorCategory.TRANSIENT,
            ErrorCategory.CONFLICT,
        ]
    )
    
    def should_retry(
        self,
        error_info: ErrorInfo,
        attempt: int
    ) -> bool:
        """
        Проверить нужно ли retry.
        
        ARGS:
        - error_info: Информация об ошибке
        - attempt: Номер попытки (0-based)
        
        RETURNS:
        - True если можно retry
        """
        # Проверка количества попыток
        if attempt >= self.max_retries:
            return False
        
        # Проверка категории
        if error_info.category not in self.retryable_categories:
            return False
        
        # Проверка серьезности
        if error_info.severity == ErrorSeverity.CRITICAL:
            return False
        
        return True
    
    def get_delay(self, attempt: int) -> float:
        """
        Вычислить задержку перед retry.
        
        ФОРМУЛА:
        delay = min(base_delay * (exponential_base ^ attempt), max_delay) + jitter
        
        ARGS:
        - attempt: Номер попытки (0-based)
        
        RETURNS:
        - Задержка в секундах
        """
        # Экспоненциальная задержка
        exponential_delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap на максимальную задержку
        capped_delay = min(exponential_delay, self.max_delay)
        
        # Добавляем джиттер
        jitter_value = random.uniform(0, self.jitter)
        
        return capped_delay + jitter_value
    
    def get_total_max_delay(self) -> float:
        """
        Максимальная общая задержка всех retry.
        
        RETURNS:
        - Суммарная задержка в секундах
        """
        total = 0.0
        for attempt in range(self.max_retries):
            total += self.get_delay(attempt)
        return total
    
    def __repr__(self) -> str:
        return (
            f"RetryPolicy(max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"max_delay={self.max_delay}s)"
        )


# ============================================================
# Error Handler
# ============================================================

class ErrorHandler:
    """
    Централизованный обработчик ошибок.
    
    ФУНКЦИИ:
    1. Классификация ошибок
    2. Логирование
    3. Публикация событий
    4. Стратегии восстановления
    
    USAGE:
    ```python
    handler = ErrorHandler()
    
    # Классификация
    error_info = await handler.classify(exception)
    
    # Обработка
    await handler.handle(
        exception,
        component="my_component",
        operation="my_operation"
    )
    ```
    """
    
    def __init__(self, event_bus=None):
        """
        Инициализация обработчика.
        
        ARGS:
        - event_bus: EventBus для публикации событий (optional)
        """
        self._event_bus = event_bus
        self._error_handlers: Dict[Type[Exception], callable] = {}
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def register_handler(
        self,
        error_type: Type[Exception],
        handler: callable
    ) -> None:
        """
        Зарегистрировать обработчик для типа ошибки.
        
        ARGS:
        - error_type: Тип исключения
        - handler: Функция обработчика
        """
        self._error_handlers[error_type] = handler
    
    async def classify(self, error: Exception) -> ErrorInfo:
        """
        Классифицировать ошибку.
        
        ARGS:
        - error: Исключение для классификации
        
        RETURNS:
        - ErrorInfo с категорией и серьезностью
        """
        category = self._categorize_error(error)
        severity = self._determine_severity(error, category)
        
        return ErrorInfo(
            error=error,
            category=category,
            severity=severity,
        )
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Определить категорию ошибки.
        
        ЛОГИКА:
        - TimeoutError, ConnectionError → TRANSIENT
        - ValueError, TypeError → INVALID_INPUT
        - FileNotFoundError, KeyError → NOT_FOUND
        - RuntimeError с "conflict" → CONFLICT
        - Остальное → UNKNOWN
        """
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # TRANSIENT: временные ошибки
        transient_keywords = [
            'timeout', 'connection', 'temporary', 'busy',
            'unavailable', 'transient', 'network'
        ]
        transient_types = (
            TimeoutError,
            ConnectionError,
            ConnectionRefusedError,
            ConnectionAbortedError,
        )
        
        if isinstance(error, transient_types):
            return ErrorCategory.TRANSIENT
        
        if any(kw in error_str for kw in transient_keywords):
            return ErrorCategory.TRANSIENT
        
        # INVALID_INPUT: ошибки валидации
        invalid_types = (
            ValueError,
            TypeError,
            AttributeError,
        )
        
        if isinstance(error, invalid_types):
            return ErrorCategory.INVALID_INPUT
        
        # NOT_FOUND: ресурс не найден
        not_found_keywords = ['not found', 'missing', 'does not exist']
        not_found_types = (
            FileNotFoundError,
            KeyError,
            IndexError,
        )
        
        if isinstance(error, not_found_types):
            return ErrorCategory.NOT_FOUND
        
        if any(kw in error_str for kw in not_found_keywords):
            return ErrorCategory.NOT_FOUND
        
        # CONFLICT: конфликт
        conflict_keywords = ['conflict', 'duplicate', 'already exists']
        
        if any(kw in error_str for kw in conflict_keywords):
            return ErrorCategory.CONFLICT
        
        # FATAL: критические ошибки
        fatal_types = (
            SystemError,
            MemoryError,
            RecursionError,
        )
        
        if isinstance(error, fatal_types):
            return ErrorCategory.FATAL
        
        # UNKNOWN: всё остальное
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(
        self,
        error: Exception,
        category: ErrorCategory
    ) -> ErrorSeverity:
        """
        Определить серьезность ошибки.
        
        ЛОГИКА:
        - FATAL категория → CRITICAL
        - INVALID_INPUT → LOW
        - NOT_FOUND → MEDIUM
        - TRANSIENT → зависит от контекста
        """
        if category == ErrorCategory.FATAL:
            return ErrorSeverity.CRITICAL
        
        if category == ErrorCategory.INVALID_INPUT:
            return ErrorSeverity.LOW
        
        if category == ErrorCategory.NOT_FOUND:
            return ErrorSeverity.MEDIUM
        
        if category == ErrorCategory.TRANSIENT:
            # Временные ошибки могут быть серьезными
            if isinstance(error, (ConnectionError, TimeoutError)):
                return ErrorSeverity.HIGH
            return ErrorSeverity.MEDIUM
        
        if category == ErrorCategory.CONFLICT:
            return ErrorSeverity.MEDIUM
        
        # UNKNOWN по умолчанию
        return ErrorSeverity.MEDIUM
    
    async def handle(
        self,
        error: Exception,
        component: str = "unknown",
        operation: str = "unknown",
        severity: Optional[ErrorSeverity] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ErrorInfo:
        """
        Обработать ошибку.
        
        ARGS:
        - error: Исключение
        - component: Компонент где произошла ошибка
        - operation: Операция которая выполнялась
        - severity: Серьезность (переопределяет авто-определение)
        - metadata: Дополнительные метаданные
        
        RETURNS:
        - ErrorInfo с информацией об ошибке
        """
        # Классификация
        error_info = await self.classify(error)
        
        # Переопределяем severity если указано
        if severity:
            error_info.severity = severity
        
        # Добавляем контекст
        error_info.component = component
        error_info.operation = operation
        error_info.metadata = metadata or {}
        
        # Логирование
        await self._log_error(error_info)
        
        # Вызов зарегистрированного обработчика
        await self._call_custom_handler(error_info)
        
        # Публикация события
        await self._publish_event(error_info)
        
        return error_info
    
    async def _log_error(self, error_info: ErrorInfo) -> None:
        """Логирование ошибки."""
        log_level = self._get_log_level(error_info.severity)
        
        message = (
            f"Error in {error_info.component}.{error_info.operation}: "
            f"[{error_info.category.value}] {error_info.error_type} - "
            f"{error_info.error_message}"
        )
        
        self._logger.log(log_level, message)
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self._logger.exception("Critical error occurred")
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Получить уровень логирования по серьезности."""
        levels = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }
        return levels.get(severity, logging.ERROR)
    
    async def _call_custom_handler(self, error_info: ErrorInfo) -> None:
        """Вызов зарегистрированного обработчика."""
        error_type = type(error_info.error)
        
        # Ищем точный match
        if error_type in self._error_handlers:
            handler = self._error_handlers[error_type]
            await self._invoke_handler(handler, error_info)
            return
        
        # Ищем handler для базового класса
        for base_type in error_type.__mro__:
            if base_type in self._error_handlers:
                handler = self._error_handlers[base_type]
                await self._invoke_handler(handler, error_info)
                return
    
    async def _invoke_handler(
        self,
        handler: callable,
        error_info: ErrorInfo
    ) -> None:
        """Вызов обработчика."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(error_info)
            else:
                handler(error_info)
        except Exception as e:
            self._logger.error(f"Error handler failed: {e}")
    
    async def _publish_event(self, error_info: ErrorInfo) -> None:
        """Публикация события об ошибке в Event Bus."""
        if not self._event_bus:
            return
        
        try:
            await self._event_bus.publish(
                event_type="error.occurred",
                payload=error_info.to_dict(),
            )
        except Exception as e:
            self._logger.error(f"Failed to publish error event: {e}")
    
    def __repr__(self) -> str:
        return f"ErrorHandler(handlers={len(self._error_handlers)})"


# ============================================================
# Factory Functions
# ============================================================

_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler(event_bus=None) -> ErrorHandler:
    """
    Получить глобальный обработчик ошибок (синглтон).
    
    ARGS:
    - event_bus: EventBus для публикации событий
    
    RETURNS:
    - ErrorHandler экземпляр
    """
    global _global_error_handler
    
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler(event_bus)
    
    return _global_error_handler


def reset_error_handler() -> None:
    """Сбросить глобальный обработчик (для тестов)."""
    global _global_error_handler
    _global_error_handler = None


def create_error_handler(event_bus=None) -> ErrorHandler:
    """
    Создать новый обработчик ошибок.
    
    ARGS:
    - event_bus: EventBus для публикации событий
    
    RETURNS:
    - Новый ErrorHandler экземпляр
    """
    return ErrorHandler(event_bus)
