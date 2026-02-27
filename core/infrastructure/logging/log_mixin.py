"""
Миксин для добавления универсального логирования в компоненты.

USAGE:
    from core.infrastructure.logging.log_mixin import LogComponentMixin

    class MyComponent(BaseComponent, LogComponentMixin):
        async def execute(self, params):
            self.log_start("execute", params)
            try:
                result = await self._execute_impl(params)
                self.log_success("execute", result)
                return result
            except Exception as e:
                self.log_error("execute", e)
                raise
"""
import functools
import inspect
import logging
import time
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from core.infrastructure.logging.log_config import get_log_config, LogConfig
from core.infrastructure.event_bus.event_bus import EventType, get_event_bus


logger = logging.getLogger(__name__)


class LogComponentMixin:
    """
    Миксин для добавления логирования в компоненты.
    
    EXAMPLE:
        class MySkill(BaseSkill, LogComponentMixin):
            async def execute(self, capability, parameters, context):
                self.log_start("execute", {
                    'capability': capability.name,
                    'parameters': parameters
                })
                try:
                    result = await self._execute_impl(capability, parameters, context)
                    self.log_success("execute", result)
                    return result
                except Exception as e:
                    self.log_error("execute", e)
                    raise
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._log_config = get_log_config()
    
    def log_start(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Логирование начала операции.
        
        ARGS:
            operation: имя операции
            parameters: параметры операции (опционально)
        """
        if not self._log_config.log_execution_start:
            return
        
        message = f"▶️ {self._get_component_name()}.{operation}"
        if parameters and self._log_config.log_parameters:
            sanitized = self._sanitize_data(parameters)
            message += f" | Params: {sanitized}"
        
        self._logger.info(message)
        
        # Публикация в EventBus
        if self._log_config.enable_event_bus:
            self._publish_event(
                EventType.EXECUTION_STARTED,
                operation,
                parameters or {}
            )
    
    def log_success(
        self,
        operation: str,
        result: Any = None,
        duration_ms: float = None
    ) -> None:
        """
        Логирование успешного завершения.
        
        ARGS:
            operation: имя операции
            result: результат выполнения (опционально)
            duration_ms: длительность выполнения в мс (опционально)
        """
        if not self._log_config.log_execution_end:
            return
        
        message = f"✅ {self._get_component_name()}.{operation}"
        if duration_ms is not None and self._log_config.log_duration:
            message += f" | Duration: {duration_ms:.2f}ms"
        if result is not None and self._log_config.log_result:
            sanitized = self._sanitize_data(result)
            message += f" | Result: {sanitized}"
        
        self._logger.info(message)
        
        # Публикация в EventBus
        if self._log_config.enable_event_bus:
            self._publish_event(
                EventType.EXECUTION_COMPLETED,
                operation,
                {'result': result} if result is not None else {},
                duration_ms
            )
    
    def log_error(
        self,
        operation: str,
        error: Exception,
        duration_ms: float = None
    ) -> None:
        """
        Логирование ошибки.
        
        ARGS:
            operation: имя операции
            error: исключение
            duration_ms: длительность выполнения в мс (опционально)
        """
        if not self._log_config.log_errors:
            return
        
        message = f"❌ {self._get_component_name()}.{operation} | Error: {str(error)}"
        if duration_ms is not None:
            message += f" | Duration: {duration_ms:.2f}ms"
        
        self._logger.exception(message)
        
        # Публикация в EventBus
        if self._log_config.enable_event_bus:
            self._publish_event(
                EventType.EXECUTION_FAILED,
                operation,
                {'error': str(error)},
                duration_ms,
                success=False
            )
    
    def log_with_timing(self, operation: str, func: callable, *args, **kwargs) -> Any:
        """
        Логирование выполнения с автоматическим замером времени.
        
        USAGE:
            result = self.log_with_timing("process_data", self._process_data, data)
        
        ARGS:
            operation: имя операции
            func: функция для выполнения
            *args, **kwargs: аргументы функции
        
        RETURNS:
            результат выполнения функции
        """
        self.log_start(operation, kwargs)
        start_time = time.perf_counter()
        
        try:
            if inspect.iscoroutinefunction(func):
                raise RuntimeError("Для асинхронных функций используйте async_log_with_timing")
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_success(operation, result, duration_ms)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_error(operation, e, duration_ms)
            raise
    
    async def async_log_with_timing(self, operation: str, func: callable, *args, **kwargs) -> Any:
        """
        Асинхронное логирование выполнения с автоматическим замером времени.
        
        USAGE:
            result = await self.async_log_with_timing("process_data", self._process_data, data)
        
        ARGS:
            operation: имя операции
            func: асинхронная функция для выполнения
            *args, **kwargs: аргументы функции
        
        RETURNS:
            результат выполнения функции
        """
        self.log_start(operation, kwargs)
        start_time = time.perf_counter()
        
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_success(operation, result, duration_ms)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_error(operation, e, duration_ms)
            raise
    
    def _get_component_name(self) -> str:
        """Получение имени компонента."""
        if hasattr(self, 'name'):
            return self.name
        return self.__class__.__name__
    
    def _sanitize_data(self, data: Any) -> Any:
        """
        Санитизация данных (удаление чувствительной информации).
        
        ARGS:
            data: данные для санитизации
        
        RETURNS:
            санитизированные данные
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in [excl.lower() for excl in self._log_config.exclude_parameters]:
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, str) and len(value) > self._log_config.max_parameter_length:
                    sanitized[key] = value[:self._log_config.max_parameter_length] + "... (truncated)"
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, str) and len(data) > self._log_config.max_result_length:
            return data[:self._log_config.max_result_length] + "... (truncated)"
        return data
    
    def _publish_event(
        self,
        event_type: EventType,
        operation: str,
        data: Dict[str, Any],
        duration_ms: float = None,
        success: bool = True
    ):
        """
        Публикация события в EventBus.
        
        ARGS:
            event_type: тип события
            operation: имя операции
            data: данные события
            duration_ms: длительность выполнения в мс (опционально)
            success: успешность выполнения
        """
        try:
            if hasattr(self, 'application_context') and self.application_context:
                event_bus = self.application_context.infrastructure_context.event_bus

                event_data = {
                    'component_name': self._get_component_name(),
                    'operation': operation,
                    'timestamp': datetime.now().isoformat(),
                    'success': success,
                    **data
                }

                if duration_ms is not None:
                    event_data['duration_ms'] = duration_ms

                import asyncio
                asyncio.create_task(
                    event_bus.publish(event_type, data=event_data, source=self._get_component_name())
                )
        except Exception as e:
            self._logger.warning(f"Failed to publish event: {e}")


# ============================================================================
# ДЕКORAТОР ДЛЯ АВТОМАТИЧЕСКОГО ЛОГИРОВАНИЯ
# ============================================================================

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
    op_name = operation_name or func.__name__

    component_name = "unknown"
    component_type = "unknown"
    if args and hasattr(args[0], '__class__'):
        component_name = args[0].__class__.__name__
        component_type = getattr(args[0], 'component_type', 'unknown')

    if config.log_execution_start:
        log_message = f"▶️ START: {op_name}"
        if log_params:
            sanitized_params = _sanitize_params(kwargs, config)
            log_message += f" | Params: {sanitized_params}"
        logger.log(getattr(logging, log_level), log_message)

        if config.enable_event_bus:
            await _publish_event(
                "execution_started",
                component_name,
                component_type,
                op_name,
                kwargs if log_params else {}
            )

    start_time = time.perf_counter()

    try:
        result = await func(*args, **kwargs)
        duration = time.perf_counter() - start_time

        if config.log_execution_end:
            log_message = f"✅ SUCCESS: {op_name} | Duration: {duration*1000:.2f}ms"
            if log_result and config.log_result:
                sanitized_result = _sanitize_result(result, config)
                log_message += f" | Result: {sanitized_result}"
            logger.log(getattr(logging, log_level), log_message)

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

        if config.log_errors:
            logger.exception(
                f"❌ ERROR: {op_name} | Duration: {duration*1000:.2f}ms | Error: {str(e)}"
            )

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
    op_name = operation_name or func.__name__

    component_name = "unknown"
    component_type = "unknown"
    if args and hasattr(args[0], '__class__'):
        component_name = args[0].__class__.__name__
        component_type = getattr(args[0], 'component_type', 'unknown')

    if config.log_execution_start:
        log_message = f"▶️ START: {op_name}"
        if log_params:
            sanitized_params = _sanitize_params(kwargs, config)
            log_message += f" | Params: {sanitized_params}"
        logger.log(getattr(logging, log_level), log_message)

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
                pass

    start_time = time.perf_counter()

    try:
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start_time

        if config.log_execution_end:
            log_message = f"✅ SUCCESS: {op_name} | Duration: {duration*1000:.2f}ms"
            if log_result and config.log_result:
                sanitized_result = _sanitize_result(result, config)
                log_message += f" | Result: {sanitized_result}"
            logger.log(getattr(logging, log_level), log_message)

        return result

    except Exception as e:
        duration = time.perf_counter() - start_time

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
