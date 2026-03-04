"""
Базовые классы исключений для приложения.

АРХИТЕКТУРА:
- Единая иерархия исключений
- Информативные сообщения об ошибках
- Контекст для отладки
- Интеграция с ErrorHandler

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
```python
from core.errors.exceptions import AgentError, ValidationError

# Выбрасывание ошибки
raise ValidationError("Invalid input", field="goal")

# Обработка
try:
    # ... код ...
except AgentError as e:
    # Обработка ошибки
```
"""
from typing import Any, Dict, Optional
from datetime import datetime


class AgentBaseError(Exception):
    """
    Базовый класс для всех исключений агента.
    
    ATTRIBUTES:
    - message: сообщение об ошибке
    - code: код ошибки для API
    - metadata: дополнительные метаданные
    - timestamp: время возникновения
    """
    
    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "type": type(self).__name__,
            "message": self.message,
            "code": self.code,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


# === Agent Errors ===

class AgentError(AgentBaseError):
    """Ошибка агента."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AGENT_ERROR", **kwargs)


class AgentInitializationError(AgentError):
    """Ошибка инициализации агента."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AGENT_INIT_ERROR", **kwargs)


class AgentExecutionError(AgentError):
    """Ошибка выполнения агента."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AGENT_EXEC_ERROR", **kwargs)


class AgentTimeoutError(AgentExecutionError):
    """Превышено время выполнения агента."""
    def __init__(self, message: str = "Agent execution timed out", **kwargs):
        super().__init__(message, code="AGENT_TIMEOUT", **kwargs)


class AgentMaxStepsError(AgentExecutionError):
    """Превышено максимальное количество шагов."""
    def __init__(self, message: str = "Max steps exceeded", **kwargs):
        super().__init__(message, code="AGENT_MAX_STEPS", **kwargs)


# === Component Errors ===

class ComponentError(AgentBaseError):
    """Ошибка компонента."""
    def __init__(self, message: str, component: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if component:
            metadata["component"] = component
        super().__init__(message, metadata=metadata, **kwargs)


class ComponentInitializationError(ComponentError):
    """Ошибка инициализации компонента."""
    def __init__(self, message: str, component: str = None, **kwargs):
        super().__init__(message, component=component, **kwargs)
        self.code = "COMPONENT_INIT_ERROR"


class ComponentNotFoundError(ComponentError):
    """Компонент не найден."""
    def __init__(self, component: str, **kwargs):
        super().__init__(
            f"Component '{component}' not found",
            component=component,
            **kwargs
        )
        self.code = "COMPONENT_NOT_FOUND"


class ComponentExecutionError(ComponentError):
    """Ошибка выполнения компонента."""
    def __init__(self, message: str, component: str = None, **kwargs):
        super().__init__(message, component=component, **kwargs)
        self.code = "COMPONENT_EXEC_ERROR"


# === Validation Errors ===

class ValidationError(AgentBaseError):
    """Ошибка валидации."""
    def __init__(
        self,
        message: str,
        field: str = None,
        value: Any = None,
        **kwargs
    ):
        metadata = kwargs.pop("metadata", {})
        if field:
            metadata["field"] = field
        if value is not None:
            metadata["value"] = str(value)
        super().__init__(message, code="VALIDATION_ERROR", metadata=metadata, **kwargs)


class ConfigurationError(AgentBaseError):
    """Ошибка конфигурации."""
    def __init__(self, message: str, key: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if key:
            metadata["config_key"] = key
        super().__init__(message, code="CONFIG_ERROR", metadata=metadata, **kwargs)


# === Provider Errors ===

class ProviderError(AgentBaseError):
    """Ошибка провайдера."""
    def __init__(self, message: str, provider: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if provider:
            metadata["provider"] = provider
        super().__init__(message, code="PROVIDER_ERROR", metadata=metadata, **kwargs)


class ProviderInitializationError(ProviderError):
    """Ошибка инициализации провайдера."""
    def __init__(self, message: str, provider: str = None, **kwargs):
        super().__init__(message, provider=provider, code="PROVIDER_INIT_ERROR", **kwargs)


class ProviderConnectionError(ProviderError):
    """Ошибка соединения с провайдером."""
    def __init__(self, message: str, provider: str = None, **kwargs):
        super().__init__(message, provider=provider, code="PROVIDER_CONNECTION_ERROR", **kwargs)


# === Storage Errors ===

class StorageError(AgentBaseError):
    """Ошибка хранилища."""
    def __init__(self, message: str, storage: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if storage:
            metadata["storage"] = storage
        super().__init__(message, code="STORAGE_ERROR", metadata=metadata, **kwargs)


class StorageNotFoundError(StorageError):
    """Ресурс хранилища не найден."""
    def __init__(self, resource: str, storage: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        metadata["resource"] = resource
        super().__init__(
            f"Resource '{resource}' not found",
            storage=storage,
            code="STORAGE_NOT_FOUND",
            metadata=metadata,
            **kwargs
        )


# === Security Errors ===

class SecurityError(AgentBaseError):
    """Ошибка безопасности."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="SECURITY_ERROR", **kwargs)


class AuthenticationError(SecurityError):
    """Ошибка аутентификации."""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, code="AUTH_ERROR", **kwargs)


class AuthorizationError(SecurityError):
    """Ошибка авторизации."""
    def __init__(self, message: str = "Authorization failed", **kwargs):
        super().__init__(message, code="AUTHZ_ERROR", **kwargs)


# === Contract Errors ===

class ContractError(AgentBaseError):
    """Ошибка контракта."""
    def __init__(self, message: str, contract: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if contract:
            metadata["contract"] = contract
        super().__init__(message, code="CONTRACT_ERROR", metadata=metadata, **kwargs)


class ContractValidationError(ContractError):
    """Ошибка валидации контракта."""
    def __init__(self, message: str, contract: str = None, **kwargs):
        super().__init__(message, contract=contract, code="CONTRACT_VALIDATION_ERROR", **kwargs)


# === Prompt Errors ===

class PromptError(AgentBaseError):
    """Ошибка промпта."""
    def __init__(self, message: str, prompt: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if prompt:
            metadata["prompt"] = prompt
        super().__init__(message, code="PROMPT_ERROR", metadata=metadata, **kwargs)


class PromptNotFoundError(PromptError):
    """Промпт не найден."""
    def __init__(self, prompt: str, version: str = None, **kwargs):
        metadata = kwargs.pop("metadata", {})
        if version:
            metadata["version"] = version
        super().__init__(
            f"Prompt '{prompt}' not found",
            prompt=prompt,
            code="PROMPT_NOT_FOUND",
            metadata=metadata,
            **kwargs
        )
