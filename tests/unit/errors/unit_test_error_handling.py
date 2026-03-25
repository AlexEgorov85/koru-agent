"""
Юнит-тесты для Error Handling.

ЗАПУСК:
```bash
pytest tests/unit/errors/test_error_handling.py -v
```
"""
import pytest
import asyncio
from core.errors.error_handler import (
    ErrorHandler,
    RetryPolicy,
    ErrorCategory,
    ErrorSeverity,
    ErrorInfo,
    get_error_handler,
    reset_error_handler,
    create_error_handler,
)


# ============================================================
# Test ErrorCategory & ErrorSeverity
# ============================================================

class TestErrorCategory:
    """Тесты ErrorCategory enum."""
    
    def test_categories_exist(self):
        """Тест: все категории существуют."""
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.INVALID_INPUT.value == "invalid_input"
        assert ErrorCategory.FATAL.value == "fatal"
        assert ErrorCategory.NOT_FOUND.value == "not_found"
        assert ErrorCategory.CONFLICT.value == "conflict"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestErrorSeverity:
    """Тесты ErrorSeverity enum."""
    
    def test_severities_exist(self):
        """Тест: все уровни существуют."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


# ============================================================
# Test ErrorInfo
# ============================================================

class TestErrorInfo:
    """Тесты ErrorInfo dataclass."""

    def test_create_error_info(self):
        """Тест: создание ErrorInfo."""
        from core.errors.error_handler import ErrorContext
        error = ValueError("test error")
        context = ErrorContext(component="test_component", operation="test_operation")
        info = ErrorInfo(
            error=error,
            context=context,
            category=ErrorCategory.INVALID_INPUT,
            severity=ErrorSeverity.LOW,
        )

        assert info.error_message == "test error"
        assert info.error_type == "ValueError"
        assert info.context.component == "test_component"
        assert info.context.operation == "test_operation"

    def test_to_dict(self):
        """Тест: конвертация в dict."""
        from core.errors.error_handler import ErrorContext
        error = ValueError("test")
        context = ErrorContext(component="unknown", operation="unknown")
        info = ErrorInfo(
            error=error,
            context=context,
            category=ErrorCategory.INVALID_INPUT,
            severity=ErrorSeverity.LOW
        )

        result = info.to_dict()

        assert "error_type" in result
        assert "error_message" in result
        assert "category" in result
        assert "severity" in result
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "test"


# ============================================================
# Test RetryPolicy
# ============================================================

class TestRetryPolicy:
    """Тесты RetryPolicy."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.jitter == 0.5
    
    def test_should_retry_transient(self):
        """Тест: retry для TRANSIENT ошибок."""
        from core.errors.error_handler import ErrorContext
        policy = RetryPolicy()
        context = ErrorContext(component="test", operation="test")
        error_info = ErrorInfo(
            error=TimeoutError("timeout"),
            context=context,
            category=ErrorCategory.TRANSIENT,
            severity=ErrorSeverity.MEDIUM
        )

        # Первые 3 попытки - retry
        assert policy.should_retry(error_info.error, 0, error_info.category, error_info.severity) is True
        assert policy.should_retry(error_info.error, 1, error_info.category, error_info.severity) is True
        assert policy.should_retry(error_info.error, 2, error_info.category, error_info.severity) is True

        # После max_retries - нет
        assert policy.should_retry(error_info.error, 3, error_info.category, error_info.severity) is False

    def test_should_retry_invalid_input(self):
        """Тест: нет retry для INVALID_INPUT."""
        from core.errors.error_handler import ErrorContext
        policy = RetryPolicy()
        context = ErrorContext(component="test", operation="test")
        error_info = ErrorInfo(
            error=ValueError("invalid"),
            context=context,
            category=ErrorCategory.INVALID_INPUT,
            severity=ErrorSeverity.LOW
        )

        assert policy.should_retry(error_info.error, 0, error_info.category, error_info.severity) is False

    def test_should_retry_fatal(self):
        """Тест: нет retry для FATAL."""
        from core.errors.error_handler import ErrorContext
        policy = RetryPolicy()
        context = ErrorContext(component="test", operation="test")
        error_info = ErrorInfo(
            error=SystemError("fatal"),
            context=context,
            category=ErrorCategory.FATAL,
            severity=ErrorSeverity.CRITICAL
        )

        assert policy.should_retry(error_info.error, 0, error_info.category, error_info.severity) is False

    def test_should_retry_critical_severity(self):
        """Тест: нет retry для CRITICAL severity."""
        from core.errors.error_handler import ErrorContext
        policy = RetryPolicy()
        context = ErrorContext(component="test", operation="test")
        error_info = ErrorInfo(
            error=ConnectionError("error"),
            context=context,
            category=ErrorCategory.TRANSIENT,
            severity=ErrorSeverity.CRITICAL
        )

        assert policy.should_retry(error_info.error, 0, error_info.category, error_info.severity) is False
    
    def test_get_delay_exponential(self):
        """Тест: экспоненциальная задержка."""
        policy = RetryPolicy(base_delay=1.0, max_delay=30.0, jitter=0)
        
        # delay = 1.0 * (2 ^ attempt)
        assert policy.get_delay(0) == 1.0   # 2^0 = 1
        assert policy.get_delay(1) == 2.0   # 2^1 = 2
        assert policy.get_delay(2) == 4.0   # 2^2 = 4
        assert policy.get_delay(3) == 8.0   # 2^3 = 8
    
    def test_get_delay_capped(self):
        """Тест: задержка capped на max_delay."""
        policy = RetryPolicy(base_delay=1.0, max_delay=10.0, jitter=0)
        
        # 2^10 = 1024, но cap на 10
        delay = policy.get_delay(10)
        assert delay == 10.0
    
    def test_get_delay_with_jitter(self):
        """Тест: задержка с джиттером."""
        policy = RetryPolicy(base_delay=1.0, jitter=0.5)
        
        delay = policy.get_delay(0)
        
        # base_delay + jitter (0 to 0.5)
        assert 1.0 <= delay <= 1.5
    
    def test_get_total_max_delay(self):
        """Тест: общая максимальная задержка."""
        policy = RetryPolicy(max_retries=3, base_delay=1.0, jitter=0)
        
        # 1 + 2 + 4 = 7
        total = policy.get_total_max_delay()
        assert total == 7.0
    
    def test_repr(self):
        """Тест: строковое представление."""
        policy = RetryPolicy(max_retries=5, base_delay=2.0)
        repr_str = repr(policy)
        
        assert "RetryPolicy" in repr_str
        assert "5" in repr_str
        assert "2.0" in repr_str


# ============================================================
# Test ErrorHandler
# ============================================================

class TestErrorHandler:
    """Тесты ErrorHandler."""
    
    @pytest.fixture
    def handler(self):
        """Создать ErrorHandler."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_classify_timeout_error(self, handler):
        """Тест: классификация TimeoutError."""
        error = TimeoutError("connection timeout")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.TRANSIENT
    
    @pytest.mark.asyncio
    async def test_classify_connection_error(self, handler):
        """Тест: классификация ConnectionError."""
        error = ConnectionError("connection lost")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.TRANSIENT
    
    @pytest.mark.asyncio
    async def test_classify_value_error(self, handler):
        """Тест: классификация ValueError."""
        error = ValueError("invalid value")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.INVALID_INPUT
    
    @pytest.mark.asyncio
    async def test_classify_type_error(self, handler):
        """Тест: классификация TypeError."""
        error = TypeError("wrong type")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.INVALID_INPUT
    
    @pytest.mark.asyncio
    async def test_classify_file_not_found(self, handler):
        """Тест: классификация FileNotFoundError."""
        error = FileNotFoundError("file not found")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_classify_key_error(self, handler):
        """Тест: классификация KeyError."""
        error = KeyError("key not found")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_classify_system_error(self, handler):
        """Тест: классификация SystemError."""
        error = SystemError("fatal error")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.FATAL
    
    @pytest.mark.asyncio
    async def test_classify_unknown_error(self, handler):
        """Тест: классификация неизвестной ошибки."""
        error = RuntimeError("unknown error")
        info = await handler.classify(error)
        
        assert info.category == ErrorCategory.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_determine_severity_fatal(self, handler):
        """Тест: серьезность для FATAL."""
        error = SystemError("fatal")
        info = await handler.classify(error)
        
        assert info.severity == ErrorSeverity.CRITICAL
    
    @pytest.mark.asyncio
    async def test_determine_severity_invalid_input(self, handler):
        """Тест: серьезность для INVALID_INPUT."""
        error = ValueError("invalid")
        info = await handler.classify(error)
        
        assert info.severity == ErrorSeverity.LOW
    
    @pytest.mark.asyncio
    async def test_determine_severity_not_found(self, handler):
        """Тест: серьезность для NOT_FOUND."""
        error = FileNotFoundError("not found")
        info = await handler.classify(error)
        
        assert info.severity == ErrorSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_handle_error(self, handler):
        """Тест: обработка ошибки."""
        error = ValueError("test error")

        info = await handler.handle(
            error,
            component="test_component",
            operation="test_operation"
        )

        assert info.error_message == "test error"
        assert info.context.component == "test_component"
        assert info.context.operation == "test_operation"

    @pytest.mark.asyncio
    async def test_handle_with_custom_severity(self, handler):
        """Тест: обработка с кастомной серьезностью."""
        error = ValueError("test")

        info = await handler.handle(
            error,
            severity=ErrorSeverity.HIGH
        )

        assert info.severity == ErrorSeverity.HIGH

    @pytest.mark.asyncio
    async def test_handle_with_metadata(self, handler):
        """Тест: обработка с метаданными."""
        error = ValueError("test")

        info = await handler.handle(
            error,
            metadata={"key": "value"}
        )

        assert info.context.metadata == {"key": "value"}
    
    def test_register_handler(self, handler):
        """Тест: регистрация обработчика."""
        called_errors = []
        
        def custom_handler(error_info):
            called_errors.append(error_info)
        
        handler.register_handler(ValueError, custom_handler)
        
        assert ValueError in handler._error_handlers
    
    @pytest.mark.asyncio
    async def test_call_custom_handler(self, handler):
        """Тест: вызов кастомного обработчика."""
        called_errors = []
        
        def custom_handler(error_info):
            called_errors.append(error_info)
        
        handler.register_handler(ValueError, custom_handler)
        
        error = ValueError("test")
        await handler.handle(error)
        
        assert len(called_errors) == 1
        assert called_errors[0].error_message == "test"
    
    @pytest.mark.asyncio
    async def test_async_custom_handler(self, handler):
        """Тест: асинхронный кастомный обработчик."""
        called_errors = []
        
        async def async_handler(error_info):
            called_errors.append(error_info)
        
        handler.register_handler(ValueError, async_handler)
        
        error = ValueError("test")
        await handler.handle(error)
        
        assert len(called_errors) == 1
    
    def test_repr(self, handler):
        """Тест: строковое представление."""
        repr_str = repr(handler)
        
        assert "ErrorHandler" in repr_str


# ============================================================
# Test Factory Functions
# ============================================================

class TestFactoryFunctions:
    """Тесты factory функций."""
    
    def teardown_method(self):
        """Сброс после каждого теста."""
        reset_error_handler()
    
    def test_get_error_handler_singleton(self):
        """Тест: get_error_handler возвращает синглтон."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2
    
    def test_reset_error_handler(self):
        """Тест: reset_error_handler сбрасывает синглтон."""
        handler1 = get_error_handler()
        reset_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is not handler2
    
    def test_create_error_handler_new_instance(self):
        """Тест: create_error_handler создает новый экземпляр."""
        handler1 = create_error_handler()
        handler2 = create_error_handler()
        
        assert handler1 is not handler2
        assert handler1 is not get_error_handler()


# ============================================================
# Test RetryPolicy Integration
# ============================================================

class TestRetryPolicyIntegration:
    """Интеграционные тесты RetryPolicy."""
    
    @pytest.mark.asyncio
    async def test_retry_loop_success(self):
        """Тест: retry loop с успехом."""
        policy = RetryPolicy(max_retries=3, jitter=0)
        handler = ErrorHandler()
        
        attempt = 0
        result = None
        
        for i in range(policy.max_retries):
            try:
                # Симуляция операции
                if i == 1:
                    result = "success"
                    break
                
                raise TimeoutError("timeout")
            except Exception as e:
                error_info = await handler.classify(e)
                
                if not policy.should_retry(error_info, i):
                    raise
                
                delay = policy.get_delay(i)
                # Не ждем реально для скорости теста
                # await asyncio.sleep(delay)
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_loop_exhausted(self):
        """Тест: retry loop исчерпан."""
        policy = RetryPolicy(max_retries=3, jitter=0)
        handler = ErrorHandler()
        
        attempts = 0
        
        for i in range(policy.max_retries):
            try:
                raise TimeoutError("timeout")
            except Exception as e:
                error_info = await handler.classify(e)
                
                if not policy.should_retry(error_info, i):
                    break
                
                attempts += 1
        
        # Все 3 попытки использованы
        assert attempts == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_for_invalid_input(self):
        """Тест: нет retry для INVALID_INPUT."""
        policy = RetryPolicy(max_retries=3)
        handler = ErrorHandler()

        attempts = 0

        try:
            raise ValueError("invalid input")
        except Exception as e:
            error_info = await handler.classify(e)

            if policy.should_retry(error_info.error, 0, error_info.category, error_info.severity):
                attempts += 1

        # Нет retry
        assert attempts == 0
