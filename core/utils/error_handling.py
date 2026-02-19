"""
Утилиты для структурированного логирования и обработки ошибок.
"""
import logging
import traceback
from typing import Any, Dict, Optional, Callable, TypeVar, ParamSpec, Generic
from functools import wraps
import asyncio

from core.models.errors import AgentError, create_error


P = ParamSpec('P')
R = TypeVar('R')


class ErrorContext:
    """
    Контекст для сбора информации об ошибке.
    
    USAGE:
        with ErrorContext("operation_name", logger) as ctx:
            # code that may fail
            pass
    """
    
    def __init__(self, operation: str, logger: logging.Logger, component: str = None):
        self.operation = operation
        self.logger = logger
        self.component = component
        self.error: Optional[Exception] = None
    
    def __enter__(self):
        self.logger.debug(f"Starting operation: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.error = exc_val
            
            error_info = {
                "operation": self.operation,
                "component": self.component,
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                "traceback": traceback.format_exc()
            }
            
            if isinstance(exc_val, AgentError):
                self.logger.error(f"Agent error in {self.operation}: {exc_val}", extra=error_info)
            else:
                self.logger.exception(f"Unexpected error in {self.operation}", extra=error_info)
        
        return False  # Don't suppress exceptions


def handle_errors(
    logger: logging.Logger = None,
    component: str = None,
    default_error_type: str = "Execution",
    reraise: bool = True
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для автоматической обработки ошибок.
    
    USAGE:
        @handle_errors(logger=my_logger, component="my_service")
        async def my_method(...):
            ...
    
    ARGS:
        logger: логгер для записи ошибок
        component: имя компонента для контекста
        default_error_type: тип ошибки по умолчанию
        reraise: если True, ошибка пробрасывается дальше
    
    RETURNS:
        Декорированная функция
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            log = logger or logging.getLogger(func.__module__)
            comp = component or func.__name__
            
            try:
                log.debug(f"Executing {comp}")
                return await func(*args, **kwargs)
            except AgentError as e:
                log.error(f"Agent error in {comp}: {e.message}", extra=e.to_dict())
                if reraise:
                    raise
            except Exception as e:
                error = create_error(
                    default_error_type,
                    str(e),
                    component=comp,
                    details={"function": func.__name__}
                )
                log.exception(f"Unexpected error in {comp}")
                if reraise:
                    raise error
        
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            log = logger or logging.getLogger(func.__module__)
            comp = component or func.__name__
            
            try:
                log.debug(f"Executing {comp}")
                return func(*args, **kwargs)
            except AgentError as e:
                log.error(f"Agent error in {comp}: {e.message}", extra=e.to_dict())
                if reraise:
                    raise
            except Exception as e:
                error = create_error(
                    default_error_type,
                    str(e),
                    component=comp,
                    details={"function": func.__name__}
                )
                log.exception(f"Unexpected error in {comp}")
                if reraise:
                    raise error
        
        # Определяем, асинхронная ли функция
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_errors(logger: logging.Logger) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Упрощённый декоратор только для логирования ошибок.
    
    USAGE:
        @log_errors(logger=my_logger)
        def my_method(...):
            ...
    """
    return handle_errors(logger=logger, reraise=True)


def safe_execute(
    func: Callable[P, R],
    *args: P.args,
    default: R = None,
    logger: logging.Logger = None,
    **kwargs: P.kwargs
) -> Optional[R]:
    """
    Безопасное выполнение функции с обработкой ошибок.
    
    USAGE:
        result = safe_execute(my_func, arg1, arg2, default=None, logger=my_logger)
    
    ARGS:
        func: функция для выполнения
        *args: аргументы функции
        default: значение по умолчанию при ошибке
        logger: логгер для записи ошибок
        **kwargs: именованные аргументы функции
    
    RETURNS:
        Результат функции или default при ошибке
    """
    log = logger or logging.getLogger(func.__module__)
    
    try:
        if asyncio.iscoroutinefunction(func):
            raise RuntimeError("safe_execute doesn't support async functions. Use safe_execute_async.")
        return func(*args, **kwargs)
    except Exception as e:
        log.exception(f"Error executing {func.__name__}: {e}")
        return default


async def safe_execute_async(
    func: Callable[P, R],
    *args: P.args,
    default: R = None,
    logger: logging.Logger = None,
    **kwargs: P.kwargs
) -> Optional[R]:
    """
    Безопасное асинхронное выполнение функции с обработкой ошибок.
    
    USAGE:
        result = await safe_execute_async(my_async_func, arg1, arg2, default=None)
    """
    log = logger or logging.getLogger(func.__module__)
    
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        log.exception(f"Error executing {func.__name__}: {e}")
        return default


class ErrorCollector:
    """
    Коллектор для сбора и агрегации ошибок.
    
    USAGE:
        collector = ErrorCollector()
        collector.add_error(error1)
        collector.add_error(error2)
        collector.raise_if_any()
    """
    
    def __init__(self, logger: logging.Logger = None):
        self.errors: list[Exception] = []
        self.logger = logger or logging.getLogger(__name__)
    
    def add_error(self, error: Exception) -> None:
        """Добавить ошибку в коллектор."""
        self.errors.append(error)
        self.logger.debug(f"Error collected: {error}")
    
    def has_errors(self) -> bool:
        """Проверка наличия ошибок."""
        return len(self.errors) > 0
    
    def clear(self) -> None:
        """Очистка коллектора."""
        self.errors.clear()
    
    def raise_if_any(self, combined_message: str = None) -> None:
        """
        Выбросить исключение если есть ошибки.
        
        ARGS:
            combined_message: сообщение для комбинированного исключения
        """
        if not self.errors:
            return
        
        if len(self.errors) == 1:
            raise self.errors[0]
        
        # Множественные ошибки
        error_messages = [str(e) for e in self.errors]
        message = combined_message or f"Multiple errors occurred: {', '.join(error_messages)}"
        raise AgentError(message, details={"errors": error_messages})
    
    def get_all(self) -> list[Exception]:
        """Получить все ошибки."""
        return self.errors.copy()
