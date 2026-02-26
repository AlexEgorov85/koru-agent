"""
Модуль обработки ошибок.

КОМПОНЕНТЫ:
- error_handler: централизованная система обработки ошибок
- exceptions: базовые классы исключений
- error_context: контекст ошибки

USAGE:
```python
from core.errors import (
    ErrorHandler,
    ErrorContext,
    ErrorSeverity,
    get_error_handler,
    AgentError,
    ValidationError,
)

# Обработка ошибки
error_handler = get_error_handler()
try:
    # ... код ...
except Exception as e:
    context = ErrorContext(component="my_component", operation="my_op")
    await error_handler.handle(e, context)

# Декоратор
@error_handler.handle_errors(component="agent", reraise=False)
async def run():
    # ... код ...
```
"""
from .error_handler import (
    ErrorHandler,
    ErrorContext,
    ErrorInfo,
    ErrorSeverity,
    ErrorCategory,
    get_error_handler,
    reset_error_handler,
)
from .exceptions import (
    # Base
    AgentBaseError,
    
    # Agent errors
    AgentError,
    AgentInitializationError,
    AgentExecutionError,
    AgentTimeoutError,
    AgentMaxStepsError,
    
    # Component errors
    ComponentError,
    ComponentInitializationError,
    ComponentNotFoundError,
    ComponentExecutionError,
    
    # Validation errors
    ValidationError,
    ConfigurationError,
    
    # Provider errors
    ProviderError,
    ProviderInitializationError,
    ProviderConnectionError,
    
    # Storage errors
    StorageError,
    StorageNotFoundError,
    
    # Security errors
    SecurityError,
    AuthenticationError,
    AuthorizationError,
    
    # Contract errors
    ContractError,
    ContractValidationError,
    
    # Prompt errors
    PromptError,
    PromptNotFoundError,
)

__all__ = [
    # Error handler
    'ErrorHandler',
    'ErrorContext',
    'ErrorInfo',
    'ErrorSeverity',
    'ErrorCategory',
    'get_error_handler',
    'reset_error_handler',
    
    # Base exception
    'AgentBaseError',
    
    # Agent exceptions
    'AgentError',
    'AgentInitializationError',
    'AgentExecutionError',
    'AgentTimeoutError',
    'AgentMaxStepsError',
    
    # Component exceptions
    'ComponentError',
    'ComponentInitializationError',
    'ComponentNotFoundError',
    'ComponentExecutionError',
    
    # Validation exceptions
    'ValidationError',
    'ConfigurationError',
    
    # Provider exceptions
    'ProviderError',
    'ProviderInitializationError',
    'ProviderConnectionError',
    
    # Storage exceptions
    'StorageError',
    'StorageNotFoundError',
    
    # Security exceptions
    'SecurityError',
    'AuthenticationError',
    'AuthorizationError',
    
    # Contract exceptions
    'ContractError',
    'ContractValidationError',
    
    # Prompt exceptions
    'PromptError',
    'PromptNotFoundError',
]
