"""
Ошибка архитектурного нарушения.

Используется для сигнализации о нарушении архитектурных принципов системы.
"""
from core.models.errors import AgentError


class ArchitectureViolationError(Exception):
    """
    Исключение, возникающее при нарушении архитектурных принципов.

    Например:
    - Использование legacy-подходов вместо современных
    - Неправильное разделение ответственностей
    - Нарушение принципов чистой архитектуры
    """
    def __init__(self, message: str):
        """
        Инициализация ошибки архитектурного нарушения.

        :param message: Сообщение об ошибке
        """
        super().__init__(message)
        self.message = message

    def __str__(self):
        return f"ArchitectureViolationError: {self.message}"


class CircularDependencyError(ArchitectureViolationError):
    """Обнаружены циклические зависимости между компонентами."""
    pass


class DependencyResolutionError(ArchitectureViolationError):
    """Ошибка разрешения зависимостей."""
    pass


class AgentStuckError(AgentError):
    """
    Агент зациклился — нет прогресса.
    
    Возникает когда:
    - Decision повторяется более 2 раз без изменения state
    - State не меняется после observe() в течение 2 consecutive steps
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class InvalidDecisionError(AgentError):
    """
    Decision некорректен.
    
    Возникает когда:
    - ACT decision без capability_name
    - capability_name не найден в доступных capabilities
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class PatternError(AgentError):
    """
    Нарушение инвариантов паттерна поведения.
    
    Возникает когда:
    - observe() не мутировал state.history
    - generate_decision() не выполнил требования паттерна
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class InfrastructureError(AgentError):
    """
    Инфраструктурная ошибка.
    
    Возникает когда:
    - LLM не был вызван когда требовался
    - Инфраструктурный сервис недоступен
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)