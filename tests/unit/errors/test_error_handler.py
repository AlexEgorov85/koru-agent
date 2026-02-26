"""
Тесты для Error Handler.

TESTS:
- test_error_handler_creation: Создание обработчика
- test_register_handler: Регистрация обработчика
- test_handle_error: Обработка ошибки
- test_handle_with_decorator: Обработка через декоратор
- test_error_severity: Уровни серьезности
- test_error_stats: Статистика ошибок
- test_custom_exceptions: Кастомные исключения
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.errors import (
    ErrorHandler,
    ErrorContext,
    ErrorInfo,
    ErrorSeverity,
    ErrorCategory,
    get_error_handler,
    reset_error_handler,
    AgentError,
    ValidationError,
    ComponentNotFoundError,
)
from core.infrastructure.event_bus import reset_event_bus_manager


@pytest.fixture
def error_handler():
    """Фикстура: новый обработчик ошибок."""
    reset_error_handler()
    reset_event_bus_manager()
    handler = ErrorHandler()
    yield handler
    reset_error_handler()
    reset_event_bus_manager()


@pytest.fixture
def error_context():
    """Фикстура: контекст ошибки."""
    return ErrorContext(
        component="test_component",
        operation="test_operation",
        user_id="test_user",
        request_id="test_request",
    )


class TestErrorHandlerCreation:
    """Тесты создания обработчика."""

    def test_create_error_handler(self):
        """Создание обработчика ошибок."""
        handler = ErrorHandler()
        
        assert handler is not None
        assert len(handler._handlers) > 0  # Дефолтные обработчики

    def test_get_error_handler_singleton(self):
        """get_error_handler возвращает singleton."""
        reset_error_handler()
        
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2

    def test_reset_error_handler(self):
        """Сброс singleton."""
        reset_error_handler()
        handler1 = get_error_handler()
        
        reset_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is not handler2


class TestHandlerRegistration:
    """Тесты регистрации обработчиков."""

    def test_register_handler(self, error_handler):
        """Регистрация обработчика."""
        async def custom_handler(error, context):
            return True
        
        error_handler.register_handler(
            AgentError,
            custom_handler,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.INTERNAL,
        )
        
        assert AgentError in error_handler._handlers
        assert error_handler._handlers[AgentError] == custom_handler
        assert error_handler._handler_severity[AgentError] == ErrorSeverity.HIGH

    def test_register_multiple_handlers(self, error_handler):
        """Регистрация нескольких обработчиков."""
        async def handler1(error, context):
            return True
        
        async def handler2(error, context):
            return True
        
        error_handler.register_handler(AgentError, handler1)
        error_handler.register_handler(ValidationError, handler2)
        
        assert len(error_handler._handlers) >= 2


class TestErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_handle_error(self, error_handler, error_context):
        """Обработка ошибки."""
        error = ValueError("Test error")
        
        error_info = await error_handler.handle(error, error_context)
        
        assert error_info is not None
        assert error_info.error is error
        assert error_info.context is error_context
        assert error_info.handled is True  # Дефолтный обработчик

    @pytest.mark.asyncio
    async def test_handle_with_custom_handler(self, error_handler, error_context):
        """Обработка с кастомным обработчиком."""
        handled_errors = []
        
        async def custom_handler(error, context):
            handled_errors.append((error, context))
            return True
        
        error = AgentError("Custom agent error")
        error_handler.register_handler(AgentError, custom_handler)
        
        error_info = await error_handler.handle(error, error_context)
        
        assert len(handled_errors) == 1
        assert handled_errors[0][0] is error
        assert error_info.handled is True

    @pytest.mark.asyncio
    async def test_handle_unhandled_error(self, error_handler, error_context):
        """Обработка необработанной ошибки."""
        # Регистрируем обработчик который возвращает False
        async def failing_handler(error, context):
            return False
        
        error = AgentError("Test error")
        error_handler.register_handler(AgentError, failing_handler)
        
        error_info = await error_handler.handle(error, error_context)
        
        assert error_info.handled is False

    @pytest.mark.asyncio
    async def test_handle_with_severity_override(self, error_handler, error_context):
        """Обработка с переопределением severity."""
        error = ValueError("Test error")
        
        error_info = await error_handler.handle(
            error,
            error_context,
            severity=ErrorSeverity.CRITICAL,
        )
        
        assert error_info.severity == ErrorSeverity.CRITICAL


class TestErrorHandlerDecorator:
    """Тесты декоратора обработки ошибок."""

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_async(self, error_handler):
        """Декоратор для асинхронной функции."""
        @error_handler.handle_errors(component="test", reraise=False)
        async def failing_function():
            raise ValueError("Test error")
        
        result = await failing_function()
        
        assert result is None  # reraise=False

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_reraise(self, error_handler):
        """Декоратор с reraise=True."""
        @error_handler.handle_errors(component="test", reraise=True)
        async def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await failing_function()

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self, error_handler):
        """Декоратор для успешной функции."""
        @error_handler.handle_errors(component="test")
        async def success_function():
            return "success"
        
        result = await success_function()
        
        assert result == "success"

    def test_handle_errors_decorator_sync(self, error_handler):
        """Декоратор для синхронной функции."""
        @error_handler.handle_errors(component="test", reraise=False)
        def failing_sync_function():
            raise ValueError("Test error")
        
        result = failing_sync_function()
        
        assert result is None


class TestErrorSeverity:
    """Тесты уровней серьезности."""

    @pytest.mark.asyncio
    async def test_default_severity(self, error_handler, error_context):
        """Severity по умолчанию."""
        error = ValueError("Test error")
        
        error_info = await error_handler.handle(error, error_context)
        
        assert error_info.severity == ErrorSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_validation_error_severity(self, error_handler, error_context):
        """ValidationError имеет LOW severity."""
        from pydantic import ValidationError as PydanticValidationError
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            name: str
        
        try:
            TestModel()  # Missing required field
        except PydanticValidationError as e:
            error_info = await error_handler.handle(e, error_context)
            
            assert error_info.severity == ErrorSeverity.LOW


class TestErrorStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_error_count(self, error_handler, error_context):
        """Подсчет количества ошибок."""
        error = ValueError("Test error")
        
        await error_handler.handle(error, error_context)
        await error_handler.handle(error, error_context)
        await error_handler.handle(error, error_context)
        
        stats = error_handler.get_stats()
        
        assert stats["total_errors"] == 3

    @pytest.mark.asyncio
    async def test_handled_count(self, error_handler, error_context):
        """Подсчет обработанных ошибок."""
        async def success_handler(error, context):
            return True
        
        error_handler.register_handler(ValueError, success_handler)
        
        error = ValueError("Test error")
        await error_handler.handle(error, error_context)
        await error_handler.handle(error, error_context)
        
        stats = error_handler.get_stats()
        
        assert stats["handled_errors"] == 2
        assert stats["handle_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_errors_by_type(self, error_handler, error_context):
        """Группировка ошибок по типу."""
        await error_handler.handle(ValueError("Test 1"), error_context)
        await error_handler.handle(ValueError("Test 2"), error_context)
        await error_handler.handle(TypeError("Test 3"), error_context)
        
        stats = error_handler.get_stats()
        
        assert stats["errors_by_type"]["ValueError"] == 2
        assert stats["errors_by_type"]["TypeError"] == 1

    @pytest.mark.asyncio
    async def test_reset_stats(self, error_handler, error_context):
        """Сброс статистики."""
        error = ValueError("Test error")
        await error_handler.handle(error, error_context)
        
        error_handler.reset_stats()
        
        stats = error_handler.get_stats()
        assert stats["total_errors"] == 0


class TestErrorContext:
    """Тесты контекста ошибки."""

    def test_error_context_creation(self):
        """Создание контекста ошибки."""
        context = ErrorContext(
            component="test",
            operation="test_op",
            user_id="user123",
        )
        
        assert context.component == "test"
        assert context.operation == "test_op"
        assert context.user_id == "user123"
        assert context.stack_trace is not None

    def test_error_context_to_dict(self):
        """Конвертация контекста в dict."""
        context = ErrorContext(
            component="test",
            operation="test_op",
        )
        
        data = context.to_dict()
        
        assert "component" in data
        assert "operation" in data
        assert "timestamp" in data
        assert "stack_trace" in data


class TestCustomExceptions:
    """Тесты кастомных исключений."""

    def test_agent_error(self):
        """Создание AgentError."""
        error = AgentError("Test message", metadata={"key": "value"})
        
        assert error.message == "Test message"
        assert error.code == "AGENT_ERROR"
        assert error.metadata["key"] == "value"

    def test_validation_error(self):
        """Создание ValidationError."""
        error = ValidationError(
            "Invalid value",
            field="name",
            value="test",
        )
        
        assert error.message == "Invalid value"
        assert error.code == "VALIDATION_ERROR"
        assert error.metadata["field"] == "name"
        assert error.metadata["value"] == "test"

    def test_component_not_found_error(self):
        """Создание ComponentNotFoundError."""
        error = ComponentNotFoundError(component="my_component")
        
        assert "my_component" in error.message
        assert error.code == "COMPONENT_NOT_FOUND"
        assert error.metadata["component"] == "my_component"

    def test_exception_to_dict(self):
        """Конвертация исключения в dict."""
        error = AgentError("Test", metadata={"key": "value"})
        
        data = error.to_dict()
        
        assert data["type"] == "AgentError"
        assert data["message"] == "Test"
        assert data["code"] == "AGENT_ERROR"
        assert data["metadata"]["key"] == "value"


class TestErrorCategory:
    """Тесты категорий ошибок."""

    @pytest.mark.asyncio
    async def test_timeout_error_category(self, error_handler, error_context):
        """TimeoutError имеет категорию TIMEOUT."""
        error = TimeoutError("Connection timed out")
        
        error_info = await error_handler.handle(error, error_context)
        
        assert error_info.category == ErrorCategory.TIMEOUT

    @pytest.mark.asyncio
    async def test_file_not_found_category(self, error_handler, error_context):
        """FileNotFoundError имеет категорию NOT_FOUND."""
        error = FileNotFoundError("File not found")
        
        error_info = await error_handler.handle(error, error_context)
        
        assert error_info.category == ErrorCategory.NOT_FOUND
