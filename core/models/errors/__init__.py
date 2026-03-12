"""
Единая иерархия исключений для проекта Agent_v5.

Импортируйте отсюда все кастомные исключения:
    from core.models.errors import ComponentError, ValidationError
"""

# ============================================================================
# БАЗОВЫЕ ИСКЛЮЧЕНИЯ
# ============================================================================

class AgentError(Exception):
    """
    Базовое исключение для всех ошибок системы агентов.
    
    Все кастомные исключения должны наследоваться от этого класса.
    """
    def __init__(self, message: str, component: str = None, details: dict = None):
        self.message = message
        self.component = component
        self.details = details or {}
        super().__init__(self.__str__())
    
    def __str__(self) -> str:
        base = f"{self.__class__.__name__}: {self.message}"
        if self.component:
            base += f" [component: {self.component}]"
        return base
    
    def to_dict(self) -> dict:
        """Сериализация ошибки в словарь для логирования."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "component": self.component,
            "details": self.details
        }


# ============================================================================
# ОШИБКИ КОМПОНЕНТОВ
# ============================================================================

class ComponentError(AgentError):
    """Базовое исключение для ошибок компонентов (Skills, Tools, Services)."""
    pass


class ComponentInitializationError(ComponentError):
    """Ошибка инициализации компонента."""
    pass


class ComponentNotFoundError(ComponentError):
    """Компонент не найден в реестре."""
    pass


class ComponentNotReadyError(ComponentError):
    """Компонент не готов к работе (не инициализирован)."""
    pass


# ============================================================================
# ОШИБКИ ЗАВИСИМОСТЕЙ
# ============================================================================

class DependencyError(AgentError):
    """Базовое исключение для ошибок зависимостей."""
    pass


class DependencyNotFoundError(DependencyError):
    """Зависимость не найдена."""
    pass


class CircularDependencyError(DependencyError):
    """Обнаружена циклическая зависимость."""
    pass


class DependencyResolutionError(DependencyError):
    """Ошибка разрешения зависимостей."""
    pass


# ============================================================================
# ОШИБКИ ВАЛИДАЦИИ
# ============================================================================

class ValidationError(AgentError):
    """Базовое исключение для ошибок валидации."""
    pass


class ContractValidationError(ValidationError):
    """Ошибка валидации контракта."""
    pass


class PromptValidationError(ValidationError):
    """Ошибка валидации промпта."""
    pass


class ManifestValidationError(ValidationError):
    """Ошибка валидации манифеста."""
    pass


class InputValidationError(ValidationError):
    """Ошибка валидации входных данных."""
    pass


# ============================================================================
# ОШИБКИ ВЫПОЛНЕНИЯ
# ============================================================================

class ExecutionError(AgentError):
    """Базовое исключение для ошибок выполнения."""
    pass


class ToolExecutionError(ExecutionError):
    """Ошибка выполнения инструмента."""
    pass


class ServiceExecutionError(ExecutionError):
    """Ошибка выполнения сервиса."""
    pass


class SkillExecutionError(ExecutionError):
    """Ошибка выполнения навыка."""
    pass


class TimeoutError(ExecutionError):
    """Превышено время выполнения операции."""
    pass


# ============================================================================
# ОШИБКИ ДАННЫХ
# ============================================================================

class DataError(AgentError):
    """Базовое исключение для ошибок данных."""
    pass


class DataNotFoundError(DataError):
    """Данные не найдены."""
    pass


class DataValidationError(DataError):
    """Ошибка валидации данных."""
    pass


class DatabaseError(DataError):
    """Ошибка базы данных."""
    pass


# ============================================================================
# ОШИБКИ КОНФИГУРАЦИИ
# ============================================================================

class ConfigurationError(AgentError):
    """Базовое исключение для ошибок конфигурации."""
    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Конфигурация не найдена."""
    pass


class ConfigurationValidationError(ConfigurationError):
    """Ошибка валидации конфигурации."""
    pass


# ============================================================================
# ОШИБКИ ВЕРСИОНИРОВАНИЯ
# ============================================================================

class VersionError(AgentError):
    """Базовое исключение для ошибок версионирования."""
    pass


class VersionNotFoundError(VersionError):
    """Версия компонента не найдена."""
    pass


class VersionConflictError(VersionError):
    """Конфликт версий компонентов."""
    pass


# ============================================================================
# ОШИБКИ АРХИТЕКТУРЫ (импорт из существующих)
# ============================================================================

from .architecture_violation import (
    ArchitectureViolationError,
    CircularDependencyError as ArchitectureCircularDependencyError,
    DependencyResolutionError as ArchitectureDependencyResolutionError,
    AgentStuckError,
    InvalidDecisionError,
    PatternError,
    InfrastructureError
)

# ============================================================================
# ОШИБКИ СЕРВИСА (импорт из существующих)
# ============================================================================

from .service_not_ready import ServiceNotReadyError

# ============================================================================
# ОШИБКИ СТРУКТУРИРОВАННОГО ВЫВОДА (импорт из существующих)
# ============================================================================

from .structured_output import StructuredOutputError

# ============================================================================
# FABRIC METHOD ДЛЯ СОЗДАНИЯ ОШИБОК
# ============================================================================

def create_error(error_type: str, message: str, **kwargs) -> AgentError:
    """
    Фабричный метод для создания исключений по имени типа.
    
    USAGE:
        error = create_error("ComponentInitializationError", "Failed to init")
        raise error
    
    ARGS:
        error_type: имя типа ошибки (без суффикса Error)
        message: сообщение об ошибке
        **kwargs: дополнительные параметры для конструктора
    
    RETURNS:
        Экземпляр соответствующего исключения
    """
    error_classes = {
        "Component": ComponentError,
        "ComponentInitialization": ComponentInitializationError,
        "ComponentNotFound": ComponentNotFoundError,
        "ComponentNotReady": ComponentNotReadyError,
        "Dependency": DependencyError,
        "DependencyNotFound": DependencyNotFoundError,
        "CircularDependency": CircularDependencyError,
        "DependencyResolution": DependencyResolutionError,
        "Validation": ValidationError,
        "ContractValidation": ContractValidationError,
        "PromptValidation": PromptValidationError,
        "ManifestValidation": ManifestValidationError,
        "InputValidation": InputValidationError,
        "Execution": ExecutionError,
        "ToolExecution": ToolExecutionError,
        "ServiceExecution": ServiceExecutionError,
        "SkillExecution": SkillExecutionError,
        "Timeout": TimeoutError,
        "Data": DataError,
        "DataNotFound": DataNotFoundError,
        "DataValidation": DataValidationError,
        "Database": DatabaseError,
        "Configuration": ConfigurationError,
        "ConfigurationNotFound": ConfigurationNotFoundError,
        "ConfigurationValidation": ConfigurationValidationError,
        "Version": VersionError,
        "VersionNotFound": VersionNotFoundError,
        "VersionConflict": VersionConflictError,
        "ArchitectureViolation": ArchitectureViolationError,
        "ServiceNotReady": ServiceNotReadyError,
        "StructuredOutput": StructuredOutputError,
    }
    
    error_class = error_classes.get(error_type, AgentError)
    return error_class(message, **kwargs)


__all__ = [
    # Base
    "AgentError",
    
    # Components
    "ComponentError",
    "ComponentInitializationError",
    "ComponentNotFoundError",
    "ComponentNotReadyError",
    
    # Dependencies
    "DependencyError",
    "DependencyNotFoundError",
    "CircularDependencyError",
    "DependencyResolutionError",
    
    # Validation
    "ValidationError",
    "ContractValidationError",
    "PromptValidationError",
    "ManifestValidationError",
    "InputValidationError",
    
    # Execution
    "ExecutionError",
    "ToolExecutionError",
    "ServiceExecutionError",
    "SkillExecutionError",
    "TimeoutError",
    
    # Data
    "DataError",
    "DataNotFoundError",
    "DataValidationError",
    "DatabaseError",
    
    # Configuration
    "ConfigurationError",
    "ConfigurationNotFoundError",
    "ConfigurationValidationError",
    
    # Versioning
    "VersionError",
    "VersionNotFoundError",
    "VersionConflictError",
    
    # Architecture
    "ArchitectureViolationError",
    "AgentStuckError",
    "InvalidDecisionError",
    "PatternError",
    "InfrastructureError",
    
    # Service
    "ServiceNotReadyError",
    
    # Structured output
    "StructuredOutputError",
    
    # Factory
    "create_error",
]
