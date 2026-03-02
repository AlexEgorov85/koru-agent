"""
Централизованная система обработки ошибок.

АРХИТЕКТУРА:
- Единый менеджер обработки всех ошибок приложения
- Регистрация обработчиков по типам ошибок
- Публикация событий об ошибках в Event Bus
- Контекст ошибки для отладки
- Стратегии восстановления (retry, fallback, ignore)

ПРЕИМУЩЕСТВА:
- ✅ Единая точка обработки ошибок
- ✅ Согласованное логирование
- ✅ Аудит всех ошибок через Event Bus
- ✅ Гибкие стратегии восстановления
- ✅ Упрощенная отладка
"""
import asyncio
import inspect
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)


logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Уровень серьезности ошибки."""
    LOW = "low"           # Не влияет на работу
    MEDIUM = "medium"     # Влияет на часть функциональности
    HIGH = "high"         # Критическая ошибка компонента
    CRITICAL = "critical" # Критическая ошибка системы


class ErrorCategory(Enum):
    """Категория ошибки."""
    VALIDATION = "validation"       # Ошибка валидации
    AUTHENTICATION = "authentication"  # Ошибка аутентификации
    AUTHORIZATION = "authorization"    # Ошибка авторизации
    NOT_FOUND = "not_found"           # Ресурс не найден
    CONFLICT = "conflict"             # Конфликт ресурсов
    INTERNAL = "internal"             # Внутренняя ошибка
    TIMEOUT = "timeout"               # Превышено время ожидания
    RATE_LIMIT = "rate_limit"         # Превышен лимит запросов
    CONFIGURATION = "configuration"   # Ошибка конфигурации
    DEPENDENCY = "dependency"         # Ошибка зависимости


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
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "error_type": type(self.error).__name__,
            "error_message": str(self.error),
            "severity": self.severity.value,
            "category": self.category.value,
            "handled": self.handled,
            "context": self.context.to_dict(),
            "recovery_action": self.recovery_action,
        }


class ErrorHandler:
    """
    Централизованная система обработки ошибок.
    
    FEATURES:
    - Регистрация обработчиков по типам ошибок
    - Стратегии восстановления (retry, fallback, ignore)
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
    
    def __init__(self, event_bus=None):
        """
        Инициализация обработчика ошибок.

        ARGS:
        - event_bus: шина событий (опционально)
        """
        self._handlers: Dict[Type[Exception], Callable] = {}
        self._handler_severity: Dict[Type[Exception], ErrorSeverity] = {}
        self._handler_category: Dict[Type[Exception], ErrorCategory] = {}
        self._event_bus = event_bus
        
        self._error_count = 0
        self._handled_count = 0
        self._errors_by_type: Dict[str, int] = {}
        
        self._logger = logging.getLogger(f"{__name__}.ErrorHandler")
        
        # Регистрация обработчиков по умолчанию
        self._register_default_handlers()
        
        self._logger.info("ErrorHandler инициализирован")
    
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
        return True  # Считаем обработанным
    
    async def _handle_validation_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок валидации по умолчанию."""
        self._logger.warning(f"Validation error in {context.component}.{context.operation}: {error}")
        return True
    
    async def _handle_file_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок файла по умолчанию."""
        self._logger.warning(f"File error in {context.component}.{context.operation}: {error}")
        return True
    
    async def _handle_timeout_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок таймаута по умолчанию."""
        self._logger.error(f"Timeout error in {context.component}.{context.operation}: {error}")
        return True
    
    async def _handle_connection_error(self, error: Exception, context: ErrorContext) -> bool:
        """Обработчик ошибок соединения по умолчанию."""
        self._logger.error(f"Connection error in {context.component}.{context.operation}: {error}")
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
            return True
        
        error_handler.register_handler(
            MyCustomError,
            my_handler,
            severity=ErrorSeverity.HIGH
        )
        ```
        """
        self._handlers[error_type] = handler
        self._handler_severity[error_type] = severity
        self._handler_category[error_type] = category
        
        self._logger.debug(f"Зарегистрирован обработчик для {error_type.__name__}")
    
    async def handle(
        self,
        error: Exception,
        context: ErrorContext,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None
    ) -> ErrorInfo:
        """
        Обработка ошибки.
        
        ARGS:
        - error: объект ошибки
        - context: контекст ошибки
        - severity: уровень серьезности (переопределение)
        - category: категория (переопределение)
        
        RETURNS:
        - ErrorInfo: информация об обработанной ошибке
        """
        self._error_count += 1
        error_type = type(error).__name__
        self._errors_by_type[error_type] = self._errors_by_type.get(error_type, 0) + 1
        
        # Определение обработчика
        handler = self._get_handler(error)
        
        # Определение severity и category
        error_severity = severity or self._handler_severity.get(type(error), ErrorSeverity.MEDIUM)
        error_category = category or self._handler_category.get(type(error), ErrorCategory.INTERNAL)
        
        # Создание ErrorInfo
        error_info = ErrorInfo(
            error=error,
            context=context,
            severity=error_severity,
            category=error_category,
        )
        
        # Логирование ошибки
        await self._log_error(error_info)
        
        # Вызов обработчика
        handled = False
        if handler:
            try:
                if inspect.iscoroutinefunction(handler):
                    handled = await handler(error, context)
                else:
                    handled = handler(error, context)
            except Exception as handler_error:
                self._logger.error(f"Ошибка в обработчике ошибки: {handler_error}", exc_info=True)
        
        error_info.handled = handled
        error_info.handled_at = datetime.now()
        
        if handled:
            self._handled_count += 1
        
        # Публикация события об ошибке
        await self._publish_error_event(error_info)
        
        return error_info
    
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
        event_data = error_info.to_dict()
        
        await self._event_bus.publish(
            EventType.ERROR_OCCURRED,
            data=event_data,
            domain=EventDomain.COMMON,
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
        """
        def decorator(func: Callable):
            op_name = operation or func.__name__
            
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
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                context = ErrorContext(
                    component=component,
                    operation=op_name,
                )
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Для синхронных функций используем asyncio.run
                    asyncio.run(self.handle(e, context, severity=severity))
                    if reraise:
                        raise
                    return None
            
            if inspect.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
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


# Глобальный обработчик ошибок (singleton)
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Получение глобального обработчика ошибок.
    
    RETURNS:
    - ErrorHandler: глобальный экземпляр
    """
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def reset_error_handler():
    """Сброс глобального обработчика (для тестов)."""
    global _global_error_handler
    _global_error_handler = None
