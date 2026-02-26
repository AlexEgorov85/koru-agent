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
import inspect
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

from core.infrastructure.logging.log_config import get_log_config, LogConfig
from core.infrastructure.event_bus.event_bus import EventType


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
