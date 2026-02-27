"""
Тесты для универсального механизма логирования.

TESTS:
- test_log_config: тесты конфигурации логирования
- test_log_decorator: тесты декоратора логирования
- test_log_mixin: тесты миксина логирования
- test_log_formatter: тесты форматтера логов
"""
import asyncio
import logging
import pytest
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.infrastructure.logging.log_config import (
    LogConfig,
    LogLevel,
    configure_logging,
    get_log_config,
    DEFAULT_LOG_CONFIG,
)
from core.infrastructure.logging.log_mixin import (
    log_execution,
    _sanitize_params,
    _sanitize_result,
)
from core.infrastructure.logging.log_mixin import LogComponentMixin
from core.infrastructure.logging.log_formatter import (
    LogFormatter,
    setup_logging,
)


# =============================================================================
# ТЕСТЫ КОНФИГУРАЦИИ (log_config.py)
# =============================================================================

class TestLogConfig:
    """Тесты конфигурации логирования."""

    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = LogConfig()
        
        assert config.level == LogLevel.INFO
        assert config.log_execution_start is True
        assert config.log_execution_end is True
        assert config.log_parameters is True
        assert config.log_result is True
        assert config.log_errors is True
        assert config.log_duration is True
        assert config.enable_event_bus is True
        assert config.max_parameter_length == 1000
        assert config.max_result_length == 5000

    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = LogConfig(
            level=LogLevel.DEBUG,
            log_result=False,
            exclude_parameters=['password', 'secret', 'custom_field'],
            max_parameter_length=500,
        )
        
        assert config.level == LogLevel.DEBUG
        assert config.log_result is False
        assert 'custom_field' in config.exclude_parameters
        assert config.max_parameter_length == 500

    def test_configure_logging(self):
        """Тест настройки глобальной конфигурации."""
        original_config = get_log_config()
        
        try:
            new_config = LogConfig(level=LogLevel.DEBUG)
            configure_logging(new_config)
            
            assert get_log_config().level == LogLevel.DEBUG
        finally:
            # Восстановление оригинальной конфигурации
            configure_logging(original_config)

    def test_log_level_enum(self):
        """Тест перечисления уровней логирования."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


# =============================================================================
# ТЕСТЫ ДЕКОРАТОРА (log_decorator.py)
# =============================================================================

class TestLogDecorator:
    """Тесты декоратора логирования."""

    def test_sanitize_params_removes_sensitive_data(self):
        """Тест удаления чувствительных данных из параметров."""
        config = LogConfig()
        params = {
            'username': 'john',
            'password': 'secret123',
            'api_key': 'key-12345',
            'token': 'token-abcde',
        }
        
        sanitized = _sanitize_params(params, config)
        
        assert sanitized['username'] == 'john'
        assert sanitized['password'] == '***REDACTED***'
        assert sanitized['api_key'] == '***REDACTED***'
        assert sanitized['token'] == '***REDACTED***'

    def test_sanitize_params_truncates_long_strings(self):
        """Тест обрезки длинных строк."""
        config = LogConfig(max_parameter_length=10)
        params = {
            'short': 'abc',
            'long': 'a' * 100,
        }
        
        sanitized = _sanitize_params(params, config)
        
        assert sanitized['short'] == 'abc'
        assert sanitized['long'] == 'a' * 10 + '... (truncated)'

    def test_sanitize_result_truncates_long_strings(self):
        """Тест обрезки длинных результатов."""
        config = LogConfig(max_result_length=10)
        result = 'a' * 100
        
        sanitized = _sanitize_result(result, config)
        
        assert sanitized == 'a' * 10 + '... (truncated)'

    def test_sanitize_result_preserves_short_strings(self):
        """Тест сохранения коротких результатов."""
        config = LogConfig()
        result = 'short result'
        
        sanitized = _sanitize_result(result, config)
        
        assert sanitized == 'short result'

    @pytest.mark.asyncio
    async def test_log_execution_async_success(self, caplog):
        """Тест успешного выполнения асинхронной функции."""
        @log_execution()
        async def async_func(value: int) -> int:
            return value * 2
        
        with caplog.at_level(logging.INFO):
            result = await async_func(5)
        
        assert result == 10
        assert "START: async_func" in caplog.text
        assert "SUCCESS: async_func" in caplog.text

    @pytest.mark.asyncio
    async def test_log_execution_async_error(self, caplog):
        """Тест ошибки выполнения асинхронной функции."""
        @log_execution()
        async def async_func_error():
            raise ValueError("Test error")
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await async_func_error()
        
        assert "ERROR: async_func_error" in caplog.text

    def test_log_execution_sync_success(self, caplog):
        """Тест успешного выполнения синхронной функции."""
        @log_execution()
        def sync_func(value: int) -> int:
            time.sleep(0.01)  # Небольшая задержка
            return value * 2
        
        with caplog.at_level(logging.INFO):
            result = sync_func(5)
        
        assert result == 10
        assert "START: sync_func" in caplog.text
        assert "SUCCESS: sync_func" in caplog.text
        assert "Duration:" in caplog.text

    def test_log_execution_custom_operation_name(self, caplog):
        """Тест пользовательского имени операции."""
        @log_execution(operation_name="Custom Operation")
        def custom_func():
            return "result"
        
        with caplog.at_level(logging.INFO):
            custom_func()
        
        assert "START: Custom Operation" in caplog.text
        assert "SUCCESS: Custom Operation" in caplog.text


# =============================================================================
# ТЕСТЫ МИКСИНА (log_mixin.py)
# =============================================================================

class TestLogMixin:
    """Тесты миксина логирования."""

    class MockComponent(LogComponentMixin):
        """Моковый компонент для тестирования."""
        
        def __init__(self, name: str = "TestComponent"):
            self.name = name
            super().__init__()

    def test_mixin_initialization(self):
        """Тест инициализации миксина."""
        component = self.MockComponent()
        
        assert hasattr(component, '_logger')
        assert hasattr(component, '_log_config')
        assert component._get_component_name() == "TestComponent"

    def test_log_start(self, caplog):
        """Тест логирования начала операции."""
        component = self.MockComponent()
        
        with caplog.at_level(logging.INFO):
            component.log_start("test_operation", {'param': 'value'})
        
        assert "▶️ TestComponent.test_operation" in caplog.text
        assert "Params:" in caplog.text

    def test_log_success(self, caplog):
        """Тест логирования успешного завершения."""
        component = self.MockComponent()
        
        with caplog.at_level(logging.INFO):
            component.log_success("test_operation", {'result': 'ok'}, duration_ms=100.5)
        
        assert "✅ TestComponent.test_operation" in caplog.text
        assert "Duration: 100.50ms" in caplog.text

    def test_log_error(self, caplog):
        """Тест логирования ошибки."""
        component = self.MockComponent()
        
        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test error")
            except ValueError as e:
                component.log_error("test_operation", e, duration_ms=50.0)
        
        assert "❌ TestComponent.test_operation" in caplog.text
        assert "Error: Test error" in caplog.text
        assert "Duration: 50.00ms" in caplog.text

    def test_sanitize_data_dict(self):
        """Тест санитизации словаря."""
        component = self.MockComponent()
        data = {
            'username': 'john',
            'password': 'secret',
            'api_key': 'key-123',
        }
        
        sanitized = component._sanitize_data(data)
        
        assert sanitized['username'] == 'john'
        assert sanitized['password'] == '***REDACTED***'
        assert sanitized['api_key'] == '***REDACTED***'

    def test_sanitize_data_string(self):
        """Тест санитизации строки."""
        component = self.MockComponent()
        component._log_config.max_result_length = 10
        
        long_string = 'a' * 100
        sanitized = component._sanitize_data(long_string)
        
        assert sanitized == 'a' * 10 + '... (truncated)'

    @pytest.mark.asyncio
    async def test_async_log_with_timing(self, caplog):
        """Тест асинхронного логирования с замером времени."""
        component = self.MockComponent()
        
        async def async_operation(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2
        
        with caplog.at_level(logging.INFO):
            result = await component.async_log_with_timing(
                "async_op", async_operation, 5
            )
        
        assert result == 10
        assert "▶️ TestComponent.async_op" in caplog.text
        assert "✅ TestComponent.async_op" in caplog.text

    def test_log_with_timing_sync(self, caplog):
        """Тест синхронного логирования с замером времени."""
        component = self.MockComponent()
        
        def sync_operation(value: int) -> int:
            time.sleep(0.01)
            return value * 2
        
        with caplog.at_level(logging.INFO):
            result = component.log_with_timing(
                "sync_op", sync_operation, 5
            )
        
        assert result == 10
        assert "▶️ TestComponent.sync_op" in caplog.text
        assert "✅ TestComponent.sync_op" in caplog.text


# =============================================================================
# ТЕСТЫ ФОРМАТТЕРА (log_formatter.py)
# =============================================================================

class TestLogFormatter:
    """Тесты форматтера логов."""

    def test_text_formatter_basic(self):
        """Тест базового текстового форматирования."""
        formatter = LogFormatter(format_type="text", use_colors=False)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        assert "test_logger" in formatted
        assert "INFO" in formatted
        assert "Test message" in formatted

    def test_json_formatter_basic(self):
        """Тест базового JSON форматирования."""
        formatter = LogFormatter(format_type="json")
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        import json
        data = json.loads(formatted)
        
        assert data['logger'] == "test_logger"
        assert data['level'] == "INFO"
        assert data['message'] == "Test message"

    def test_text_formatter_with_colors(self):
        """Тест текстового форматирования с цветами."""
        formatter = LogFormatter(format_type="text", use_colors=True)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        assert LogFormatter.COLORS['ERROR'] in formatted
        assert LogFormatter.RESET in formatted

    def test_json_formatter_with_exception(self):
        """Тест JSON форматирования с исключением."""
        formatter = LogFormatter(format_type="json")
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        import json
        data = json.loads(formatted)
        
        assert data['message'] == "Error occurred"

    def test_setup_logging(self, caplog):
        """Тест настройки логирования."""
        logger = setup_logging(level=logging.DEBUG, format_type="text")
        
        assert logger.level == logging.DEBUG
        
        # Проверка что обработчики добавлены
        assert len(logger.handlers) > 0


# =============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# =============================================================================

class TestLoggingIntegration:
    """Интеграционные тесты системы логирования."""

    def test_full_logging_workflow(self, caplog):
        """Тест полного рабочего процесса логирования."""
        # Настройка конфигурации
        config = LogConfig(level=LogLevel.DEBUG)
        configure_logging(config)
        
        # Создание компонента
        class TestComponent(LogComponentMixin):
            def __init__(self):
                self.name = "IntegrationTest"
                super().__init__()
            
            def process(self, data: dict) -> dict:
                self.log_start("process", data)
                result = {'processed': True, **data}
                self.log_success("process", result, duration_ms=10.0)
                return result
        
        component = TestComponent()
        
        with caplog.at_level(logging.DEBUG):
            result = component.process({'key': 'value'})
        
        assert result['processed'] is True
        assert "▶️ IntegrationTest.process" in caplog.text
        assert "✅ IntegrationTest.process" in caplog.text

    def test_decorator_with_mixin(self, caplog):
        """Тест комбинации декоратора и миксина."""
        class TestComponent(LogComponentMixin):
            def __init__(self):
                self.name = "DecoratorTest"
                super().__init__()
            
            @log_execution()
            def decorated_method(self, value: int) -> int:
                return value * 2
        
        component = TestComponent()
        
        with caplog.at_level(logging.INFO):
            result = component.decorated_method(5)
        
        assert result == 10
        assert "START: decorated_method" in caplog.text
        assert "SUCCESS: decorated_method" in caplog.text
