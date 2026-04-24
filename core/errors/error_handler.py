"""
Централизованная система обработки ошибок.

АРХИТЕКТУРА:
- Единый менеджер обработки всех ошибок приложения
- Регистрация обработчиков по типам ошибок
- Публикация событий об ошибках в Event Bus
- Контекст ошибки для отладки

ПРЕИМУЩЕСТВА:
- ✅ Единая точка обработки ошибок
- ✅ Согласованное логирование
- ✅ Аудит всех ошибок через Event Bus
- ✅ Упрощенная отладка
"""
import asyncio
import inspect
import logging
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
import random
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union, TYPE_CHECKING

from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)


logger = logging.getLogger(__name__)
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


# ============================================================
# Error Category & Severity
# ============================================================

class ErrorSeverity(Enum):
    """
    Уровень серьезности ошибки.

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


class ErrorCategory(Enum):
    """
    Категория ошибки — определяет стратегию обработки.

    КАТЕГОРИИ:
    - VALIDATION: Ошибка валидации → abort
    - AUTHENTICATION: Ошибка аутентификации → abort
    - AUTHORIZATION: Ошибка авторизации → abort
    - NOT_FOUND: Ресурс не найден → handle gracefully
    - CONFLICT: Конфликт → retry с backoff
    - INTERNAL: Внутренняя ошибка → зависит от контекста
    - TIMEOUT: Превышено время ожидания → retry
    - RATE_LIMIT: Превышен лимит запросов → retry с backoff
    - CONFIGURATION: Ошибка конфигурации → abort
    - DEPENDENCY: Ошибка зависимости → retry
    - TRANSIENT: Временная ошибка → retry
    - INVALID_INPUT: Ошибка ввода → abort
    - FATAL: Критическая ошибка → fail immediately
    - UNKNOWN: Неизвестная ошибка
    """
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL = "internal"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    TRANSIENT = "transient"
    INVALID_INPUT = "invalid_input"
    FATAL = "fatal"
    UNKNOWN = "unknown"


# ============================================================
# Error Context & Info
# ============================================================

@dataclass
class ErrorContext:
    """
    Контекст ошибки для отладки.

    ATTRIBUTES:
    - component: компонент где произошла ошибка
    - operation: операция которая выполнялась
    - user_id: ID пользователя (если есть)
    - request_id: ID запроса (если есть)
    - metadata: дополнительные метаданные
    - timestamp: время возникновения ошибки
    - stack_trace: стек вызовов
    """
    component: str
    operation: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    stack_trace: Optional[str] = None

    def __post_init__(self):
        if self.stack_trace is None:
            self.stack_trace = traceback.format_exc()

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "component": self.component,
            "operation": self.operation,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
        }


@dataclass
class ErrorInfo:
    """
    Информация об ошибке.

    ATTRIBUTES:
    - error: объект ошибки
    - context: контекст ошибки
    - severity: уровень серьезности
    - category: категория ошибки
    - handled: была ли ошибка обработана
    - handled_at: время обработки
    """
    error: Exception
    context: ErrorContext
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.INTERNAL
    handled: bool = False
    handled_at: Optional[datetime] = None
    recovery_action: Optional[str] = None

    @property
    def error_message(self) -> str:
        """Текст ошибки."""
        return str(self.error)

    @property
    def error_type(self) -> str:
        """Тип исключения."""
        return type(self.error).__name__

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "handled": self.handled,
            "context": self.context.to_dict(),
            "recovery_action": self.recovery_action,
        }


# ============================================================
# Error Handler
# ============================================================

class ErrorHandler:
    """
    Централизованная система обработки ошибок.

    FEATURES:
    - Регистрация обработчиков по типам ошибок
    - RetryPolicy для повторных попыток
    - Публикация событий об ошибках
    - Статистика ошибок
    - Декораторы для автоматической обработки

    USAGE:
    ```python
    # Создание обработчика
    error_handler = ErrorHandler()

    # Регистрация обработчика для типа ошибки
    async def handle_validation_error(error, context):
        logger.warning(f"Validation failed: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True  # Ошибка обработана

    error_handler.register_handler(
        ValidationError,
        handle_validation_error,
        severity=ErrorSeverity.LOW
    )

    # Обработка ошибки
    try:
        # ... код ...
    except Exception as e:
        context = ErrorContext(component="my_component", operation="my_operation")
        await error_handler.handle(e, context)

    # Использование декоратора
    @error_handler.handle_errors(component="my_component")
    async def my_function():
        # ... код ...
    ```
    """

    def __init__(
        self,
        event_bus=None,
        retry_policy: Optional['RetryPolicy'] = None
    ):
        """
        Инициализация обработчика ошибок.

        ARGS:
        - event_bus: шина событий (опционально)
        - retry_policy: политика retry (опционально)
        """
        from core.agent.components.policy import RetryPolicy

        self._event_bus = event_bus
        self._retry_policy = retry_policy or RetryPolicy()

        self._handlers: Dict[Type[Exception], Callable] = {}
        self._error_handlers: Dict[Type[Exception], Callable] = {}  # Алиас для совместимости
        self._handler_severity: Dict[Type[Exception], ErrorSeverity] = {}
        self._handler_category: Dict[Type[Exception], ErrorCategory] = {}

        self._error_count = 0
        self._handled_count = 0
        self._errors_by_type: Dict[str, int] = {}

        self._logger = logging.getLogger(f"{__name__}.ErrorHandler")

        # Регистрация обработчиков по умолчанию
        self._register_default_handlers()

        self._logger.info("ErrorHandler инициализирован")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def _register_default_handlers(self):
        """Регистрация обработчиков по умолчанию."""

        # Exception - базовый обработчик для всех ошибок
        self.register_handler(
            Exception,
            self._handle_generic_error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTERNAL
        )

        # ValidationError - LOW severity
        from pydantic import ValidationError as PydanticValidationError
        self.register_handler(
            PydanticValidationError,
            self._handle_validation_error,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION
        )

        # FileNotFoundError - MEDIUM severity
        self.register_handler(
            FileNotFoundError,
            self._handle_file_error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NOT_FOUND
        )

        # TimeoutError - HIGH severity
        self.register_handler(
            TimeoutError,
            self._handle_timeout_error,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.TIMEOUT
        )

        # ConnectionError - HIGH severity
        self.register_handler(
            ConnectionError,
            self._handle_connection_error,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEPENDENCY
        )

    async def _handle_generic_error(self, error: Exception, context: ErrorContext) -> bool:
        """Базовый обработчик для всех ошибок."""
        self._logger.info(f"Error in {context.component}.{context.operation}: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True  # Считаем обработанным

    async def _handle_validation_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок валидации по умолчанию."""
        self._logger.warning(f"Validation error in {context.component}.{context.operation}: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True

    async def _handle_file_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок файла по умолчанию."""
        self._logger.warning(f"File error in {context.component}.{context.operation}: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True

    async def _handle_timeout_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок таймаута по умолчанию."""
        self._logger.error(f"Timeout error in {context.component}.{context.operation}: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True

    async def _handle_connection_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок соединения по умолчанию."""
        self._logger.error(f"Connection error in {context.component}.{context.operation}: {error}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True

    def register_handler(
        self,
        error_type: Type[Exception],
        handler: Callable,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.INTERNAL
    ):
        """
        Регистрация обработчика для типа ошибки.

        ARGS:
        - error_type: тип ошибки для обработки
        - handler: функция-обработчик (async или sync)
        - severity: уровень серьезности ошибки
        - category: категория ошибки

        EXAMPLE:
        ```python
        async def my_handler(error, context):
            logger.error(f"Error: {error}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return True

        error_handler.register_handler(
            MyCustomError,
            my_handler,
            severity=ErrorSeverity.HIGH
        )
        ```
        """
        self._handlers[error_type] = handler
        self._error_handlers[error_type] = handler  # Алиас для совместимости
        self._handler_severity[error_type] = severity
        self._handler_category[error_type] = category

        self._logger.debug(f"Зарегистрирован обработчик для {error_type.__name__}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    async def classify(
        self,
        error: Exception,
        component: str = "unknown",
        operation: str = "unknown"
    ) -> ErrorInfo:
        """
        Классифицировать ошибку.

        ARGS:
        - error: Исключение для классификации
        - component: Компонент где произошла ошибка
        - operation: Операция которая выполнялась

        RETURNS:
        - ErrorInfo с категорией и серьезностью
        """
        category = self._classify_category(error)
        severity = self._classify_severity(error, category)

        context = ErrorContext(component=component, operation=operation)

        return ErrorInfo(
            error=error,
            context=context,
            category=category,
            severity=severity,
        )

    async def handle(
        self,
        error: Exception,
        context: ErrorContext = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        component: str = None,
        operation: str = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ErrorInfo:
        """
        Обработка ошибки.

        ARGS:
        - error: объект ошибки
        - context: контекст ошибки (опционально)
        - severity: уровень серьезности (переопределение)
        - category: категория (переопределение)
        - component: компонент (если context не указан)
        - operation: операция (если context не указан)
        - metadata: метаданные (если context не указан)

        RETURNS:
        - ErrorInfo: информация об обработанной ошибке

        NOTE: Поддерживает два стиля вызова:
        - handle(error, context, severity, category) - полный стиль
        - handle(error, component="x", operation="y", metadata={}) - упрощенный стиль
        """
        import sys
        import traceback
        
        # Special debug for UnboundLocalError with EventType
        if isinstance(error, UnboundLocalError) and 'EventType' in str(error):
            print(f"DEBUG: UnboundLocalError with EventType detected!", file=sys.stderr)
            traceback.print_stack()
        
        # Clean up the problematic error message pattern before handling
        error_str = str(error)
        if "cannot access local variable 'EventType'" in error_str:
            # Это UnboundLocalError обёрнутый в RuntimeError — подавляем и логируем как MEDIUM
            error = RuntimeError("LLM error occurred")
            severity = ErrorSeverity.MEDIUM
        
        print(f"DEBUG handle: {type(error).__name__}: {str(error)[:100]}", file=sys.stderr)
        
        self._error_count += 1
        error_type = type(error).__name__
        self._errors_by_type[error_type] = self._errors_by_type.get(error_type, 0) + 1

        # Создание context если не указан
        if context is None:
            context = ErrorContext(
                component=component or "unknown",
                operation=operation or "unknown",
                metadata=metadata or {}
            )

        # Классификация ошибки
        error_category = category or self._classify_category(error)
        error_severity = severity or self._handler_severity.get(
            type(error),
            self._classify_severity(error, error_category)
        )

        # Создание ErrorInfo
        error_info = ErrorInfo(
            error=error,
            context=context,
            severity=error_severity,
            category=error_category,
        )

        # ✅ НОВОЕ: Проброс CRITICAL и HIGH ошибок
        # Для критических ошибок - не обрабатываем, а пробрасываем дальше
        if error_severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            await self._log_error(error_info)
            await self._publish_error_event(error_info)
            # Пробрасываем ошибку дальше
            raise error

        # Проверка retry
        if self._retry_policy.should_retry(error, 0, error_category, error_severity):
            result = await self._retry(error, context, error_info)
            if result:
                return result

        # Логирование и публикация
        return await self._log_and_publish(error, context, error_info)

    async def _retry(
        self,
        error: Exception,
        context: ErrorContext,
        error_info: ErrorInfo
    ) -> Optional[ErrorInfo]:
        """
        Попытка повторного выполнения (если возможно).

        NOTE: Этот метод вызывается когда retry возможен,
        но фактическое повторное выполнение должно быть
        реализовано в вызывающем коде.

        RETURNS:
        - ErrorInfo если retry не удался
        - None если retry успешен (вызывающий код должен handle)
        """
        self._logger.warning(
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"Retry возможен для {type(error).__name__} в {context.component}.{context.operation}"
        )
        error_info.recovery_action = "retry_recommended"
        return None

    async def _log_and_publish(
        self,
        error: Exception,
        context: ErrorContext,
        error_info: ErrorInfo
    ) -> ErrorInfo:
        """Логирование и публикация события об ошибке."""
        # Логирование ошибки
        await self._log_error(error_info)

        # Вызов обработчика
        handler = self._get_handler(error)
        handled = False
        if handler:
            try:
                # Проверка сигнатуры обработчика
                sig = inspect.signature(handler)
                params = list(sig.parameters.keys())
                
                if len(params) == 1:
                    # Обработчик принимает error_info
                    if inspect.iscoroutinefunction(handler):
                        handled = await handler(error_info)
                    else:
                        handled = handler(error_info)
                else:
                    # Обработчик принимает (error, context)
                    if inspect.iscoroutinefunction(handler):
                        handled = await handler(error, context)
                    else:
                        handled = handler(error, context)
            except Exception as handler_error:
                self._logger.error(f"Ошибка в обработчике ошибки: {handler_error}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        error_info.handled = handled
        error_info.handled_at = datetime.now()

        if handled:
            self._handled_count += 1

        # Публикация события об ошибке
        await self._publish_error_event(error_info)

        return error_info

    def _classify_category(self, error: Exception) -> ErrorCategory:
        """
        Классифицировать категорию ошибки.

        ЛОГИКА:
        - TimeoutError, ConnectionError → TRANSIENT
        - ValueError, TypeError → INVALID_INPUT
        - FileNotFoundError, KeyError → NOT_FOUND
        - RuntimeError с "conflict" → CONFLICT
        - Остальное → UNKNOWN
        """
        error_str = str(error).lower()

        # TRANSIENT: временные ошибки
        transient_types = (TimeoutError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError)
        if isinstance(error, transient_types):
            return ErrorCategory.TRANSIENT

        transient_keywords = ['timeout', 'connection', 'temporary', 'busy', 'unavailable', 'transient', 'network']
        if any(kw in error_str for kw in transient_keywords):
            return ErrorCategory.TRANSIENT

        # INVALID_INPUT: ошибки валидации
        invalid_types = (ValueError, TypeError, AttributeError)
        if isinstance(error, invalid_types):
            return ErrorCategory.INVALID_INPUT

        # NOT_FOUND: ресурс не найден
        not_found_types = (FileNotFoundError, KeyError, IndexError)
        if isinstance(error, not_found_types):
            return ErrorCategory.NOT_FOUND

        not_found_keywords = ['not found', 'missing', 'does not exist']
        if any(kw in error_str for kw in not_found_keywords):
            return ErrorCategory.NOT_FOUND

        # CONFLICT: конфликт
        if any(kw in error_str for kw in ['conflict', 'duplicate', 'already exists']):
            return ErrorCategory.CONFLICT

        # FATAL: критические ошибки
        fatal_types = (SystemError, MemoryError, RecursionError)
        if isinstance(error, fatal_types):
            return ErrorCategory.FATAL

        return ErrorCategory.UNKNOWN

    def _classify_severity(
        self,
        error: Exception,
        category: ErrorCategory
    ) -> ErrorSeverity:
        """Определить серьезность ошибки по категории."""
        if category == ErrorCategory.FATAL:
            return ErrorSeverity.CRITICAL

        if category == ErrorCategory.INVALID_INPUT:
            return ErrorSeverity.LOW

        if category == ErrorCategory.NOT_FOUND:
            return ErrorSeverity.MEDIUM

        if category == ErrorCategory.TRANSIENT:
            if isinstance(error, (ConnectionError, TimeoutError)):
                return ErrorSeverity.HIGH
            return ErrorSeverity.MEDIUM

        if category == ErrorCategory.CONFLICT:
            return ErrorSeverity.MEDIUM

        return ErrorSeverity.MEDIUM

    def _get_handler(self, error: Exception) -> Optional[Callable]:
        """Получение обработчика для типа ошибки."""
        error_type = type(error)

        # Прямой поиск
        if error_type in self._handlers:
            return self._handlers[error_type]

        # Поиск по наследству
        for registered_type, handler in self._handlers.items():
            if isinstance(error, registered_type):
                return handler

        # Обработчик по умолчанию для всех Exception
        return self._handlers.get(Exception)

    async def _log_error(self, error_info: ErrorInfo):
        """Логирование ошибки."""
        log_level = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.MEDIUM: logging.INFO,
            ErrorSeverity.HIGH: logging.WARNING,
            ErrorSeverity.CRITICAL: logging.ERROR,
        }.get(error_info.severity, logging.INFO)

        message = (
            f"Error in {error_info.context.component}.{error_info.context.operation}: "
            f"{type(error_info.error).__name__}: {error_info.error}"
        )

        self._logger.log(log_level, message, exc_info=True)

    async def _publish_error_event(self, error_info: ErrorInfo):
        """Публикация события об ошибке в Event Bus."""
        if not self._event_bus:
            self._logger.debug("Event bus не доступен, пропускаем публикацию события об ошибке")
            return

        event_data = error_info.to_dict()

        await self._event_bus.publish(
            EventType.ERROR_OCCURRED,
            data=event_data,
            source="ErrorHandler"
        )

    def handle_errors(
        self,
        component: str,
        operation: Optional[str] = None,
        reraise: bool = True,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ):
        """
        Декоратор для автоматической обработки ошибок.

        ARGS:
        - component: имя компонента
        - operation: имя операции (по умолчанию имя функции)
        - reraise: пробрасывать ли ошибку дальше
        - severity: уровень серьезности

        EXAMPLE:
        ```python
        @error_handler.handle_errors(component="agent", reraise=False)
        async def run_agent(goal: str):
            # ... код ...
        ```

        NOTE: Поддерживаются ТОЛЬКО асинхронные функции.
        """
        def decorator(func: Callable):
            op_name = operation or func.__name__

            # ПРОВЕРКА: функция должна быть асинхронной
            if not inspect.iscoroutinefunction(func):
                raise TypeError(
                    f"Function '{func.__name__}' must be async. "
                    f"Sync functions are not supported by handle_errors decorator. "
                    f"Please convert '{func.__name__}' to async."
                )

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                context = ErrorContext(
                    component=component,
                    operation=op_name,
                )
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    await self.handle(e, context, severity=severity)
                    if reraise:
                        raise
                    return None

            return async_wrapper

        return decorator

    @property
    def retry_policy(self) -> 'RetryPolicy':
        """Получить политику retry."""
        return self._retry_policy

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики ошибок."""
        return {
            "total_errors": self._error_count,
            "handled_errors": self._handled_count,
            "unhandled_errors": self._error_count - self._handled_count,
            "handle_rate": (
                self._handled_count / self._error_count * 100
                if self._error_count > 0 else 0
            ),
            "errors_by_type": self._errors_by_type.copy(),
        }

    def reset_stats(self):
        """Сброс статистики."""
        self._error_count = 0
        self._handled_count = 0
        self._errors_by_type.clear()

    def __repr__(self) -> str:
        return f"ErrorHandler(handlers={len(self._handlers)}, retry_policy={self._retry_policy})"


# ============================================================
# Фабричные функции
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


def create_error_handler(event_bus=None, retry_policy: Optional['RetryPolicy'] = None) -> ErrorHandler:
    """
    Создать новый обработчик ошибок.

    ARGS:
    - event_bus: EventBus для публикации событий
    - retry_policy: Политика retry

    RETURNS:
    - Новый ErrorHandler экземпляр
    """
    return ErrorHandler(event_bus, retry_policy)
