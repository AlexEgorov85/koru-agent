"""
Декоратор для автоматического логирования выполнения методов.

USAGE:
    from core.infrastructure.logging.log_decorator import log_execution
    
    @log_execution()
    async def execute(self, params):
        return result
    
    @log_execution(operation_name="SQL Query Execution")
    def execute_query(self, sql):
        return result
"""
import functools
import inspect
import time
from datetime import datetime
from typing import Any, Callable, Optional
import logging

from core.infrastructure.logging.log_config import get_log_config, LogConfig
from core.infrastructure.event_bus.event_bus import EventType, get_event_bus


logger = logging.getLogger(__name__)


def log_execution(
    operation_name: Optional[str] = None,
    log_level: str = "INFO",
    log_params: bool = True,
    log_result: bool = True,
):
    """
    Декоратор для автоматического логирования выполнения метода.
    
    ARGS:
        operation_name: Имя операции (по умолчанию имя метода)
        log_level: Уровень логирования
        log_params: Логировать ли параметры
        log_result: Логировать ли результат
    
    EXAMPLE:
        @log_execution()
        async def execute(self, params):
            return result
        
        @log_execution(operation_name="SQL Query Execution")
        def execute_query(self, sql):
            return result
    """
    def decorator(func: Callable) -> Callable:
        # Определяем является ли функция асинхронной
        is_async = inspect.iscoroutinefunction(func)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _log_execution_core_async(
                func, args, kwargs, operation_name, log_level, log_params, log_result
            )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _log_execution_core_sync(
                func, args, kwargs, operation_name, log_level, log_params, log_result
            )
        
        return async_wrapper if is_async else sync_wrapper
    
    return decorator


async def _log_execution_core_async(
    func: Callable,
    args: tuple,
    kwargs: dict,
    operation_name: Optional[str],
    log_level: str,
    log_params: bool,
    log_result: bool
) -> Any:
    """Асинхронное ядро логирования выполнения."""
    config = get_log_config()
    
    # Получаем имя операции
    op_name = operation_name or func.__name__
    
    # Получаем контекст компонента (если есть)
    component_name = "unknown"
    component_type = "unknown"
    if args and hasattr(args[0], '__class__'):
        component_name = args[0].__class__.__name__
        component_type = getattr(args[0], 'component_type', 'unknown')
    
    # Логирование начала выполнения
    if config.log_execution_start:
        log_message = f"▶️ START: {op_name}"
        if log_params:
            sanitized_params = _sanitize_params(kwargs, config)
            log_message += f" | Params: {sanitized_params}"
        
        logger.log(getattr(logging, log_level), log_message)
        
        # Публикация события в EventBus
        if config.enable_event_bus:
            await _publish_event(
                "execution_started",
                component_name,
                component_type,
                op_name,
                kwargs if log_params else {}
            )
    
    # Выполнение метода с замером времени
    start_time = time.perf_counter()
    start_datetime = datetime.now()
    
    try:
        result = await func(*args, **kwargs)
        
        duration = time.perf_counter() - start_time
        
        # Логирование успешного завершения
        if config.log_execution_end:
            log_message = f"✅ SUCCESS: {op_name} | Duration: {duration*1000:.2f}ms"
            if log_result and config.log_result:
                sanitized_result = _sanitize_result(result, config)
                log_message += f" | Result: {sanitized_result}"
            
            logger.log(getattr(logging, log_level), log_message)
            
            # Публикация события в EventBus
            if config.enable_event_bus:
                await _publish_event(
                    "execution_completed",
                    component_name,
                    component_type,
                    op_name,
                    {},
                    duration,
                    success=True
                )
        
        return result
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        
        # Логирование ошибки
        if config.log_errors:
            logger.exception(
                f"❌ ERROR: {op_name} | Duration: {duration*1000:.2f}ms | Error: {str(e)}"
            )
            
            # Публикация события в EventBus
            if config.enable_event_bus:
                await _publish_event(
                    "execution_failed",
                    component_name,
                    component_type,
                    op_name,
                    {},
                    duration,
                    success=False,
                    error=str(e)
                )
        
        raise


def _log_execution_core_sync(
    func: Callable,
    args: tuple,
    kwargs: dict,
    operation_name: Optional[str],
    log_level: str,
    log_params: bool,
    log_result: bool
) -> Any:
    """Синхронное ядро логирования выполнения."""
    config = get_log_config()
    
    # Получаем имя операции
    op_name = operation_name or func.__name__
    
    # Получаем контекст компонента (если есть)
    component_name = "unknown"
    component_type = "unknown"
    if args and hasattr(args[0], '__class__'):
        component_name = args[0].__class__.__name__
        component_type = getattr(args[0], 'component_type', 'unknown')
    
    # Логирование начала выполнения
    if config.log_execution_start:
        log_message = f"▶️ START: {op_name}"
        if log_params:
            sanitized_params = _sanitize_params(kwargs, config)
            log_message += f" | Params: {sanitized_params}"
        
        logger.log(getattr(logging, log_level), log_message)
        
        # Публикация события в EventBus (асинхронно, но не ждём)
        if config.enable_event_bus:
            try:
                event_bus = get_event_bus()
                event_data = {
                    'component_name': component_name,
                    'component_type': component_type,
                    'operation': op_name,
                    'timestamp': datetime.now().isoformat(),
                    'duration_ms': 0.0,
                    'success': True,
                }
                if kwargs and log_params:
                    event_data['parameters'] = _sanitize_params(kwargs, config)
                # Запускаем задачу, но не ждём её выполнения в синхронном контексте
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        event_bus.publish(
                            EventType.EXECUTION_STARTED,
                            data=event_data,
                            source=component_name
                        )
                    )
            except Exception:
                pass  # Игнорируем ошибки публикации в синхронном режиме
    
    # Выполнение метода с замером времени
    start_time = time.perf_counter()
    
    try:
        result = func(*args, **kwargs)
        
        duration = time.perf_counter() - start_time
        
        # Логирование успешного завершения
        if config.log_execution_end:
            log_message = f"✅ SUCCESS: {op_name} | Duration: {duration*1000:.2f}ms"
            if log_result and config.log_result:
                sanitized_result = _sanitize_result(result, config)
                log_message += f" | Result: {sanitized_result}"
            
            logger.log(getattr(logging, log_level), log_message)
        
        return result
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        
        # Логирование ошибки
        if config.log_errors:
            logger.exception(
                f"❌ ERROR: {op_name} | Duration: {duration*1000:.2f}ms | Error: {str(e)}"
            )
        
        raise


async def _publish_event(
    event_type: str,
    component_name: str,
    component_type: str,
    operation: str,
    params: dict,
    duration: float = 0.0,
    success: bool = True,
    error: Optional[str] = None
):
    """Публикация события логирования в EventBus."""
    try:
        event_bus = get_event_bus()
        
        event_data = {
            'component_name': component_name,
            'component_type': component_type,
            'operation': operation,
            'timestamp': datetime.now().isoformat(),
            'duration_ms': duration * 1000,
            'success': success,
        }
        
        if params:
            event_data['parameters'] = params
        
        if error:
            event_data['error'] = error
        
        # Маппинг типов событий
        event_type_map = {
            'execution_started': EventType.EXECUTION_STARTED,
            'execution_completed': EventType.EXECUTION_COMPLETED,
            'execution_failed': EventType.EXECUTION_FAILED,
        }
        
        event_type_enum = event_type_map.get(event_type, EventType.SYSTEM_ERROR)
        
        await event_bus.publish(
            event_type_enum,
            data=event_data,
            source=component_name
        )
    except Exception as e:
        logger.warning(f"Failed to publish log event: {e}")


def _sanitize_params(params: dict, config: LogConfig) -> dict:
    """Санитизация параметров (удаление чувствительных данных)."""
    sanitized = {}
    for key, value in params.items():
        if key.lower() in [excl.lower() for excl in config.exclude_parameters]:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, str) and len(value) > config.max_parameter_length:
            sanitized[key] = value[:config.max_parameter_length] + "... (truncated)"
        else:
            sanitized[key] = value
    return sanitized


def _sanitize_result(result: Any, config: LogConfig) -> Any:
    """Санитизация результата."""
    if isinstance(result, str) and len(result) > config.max_result_length:
        return result[:config.max_result_length] + "... (truncated)"
    return result
