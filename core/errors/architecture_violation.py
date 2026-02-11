"""
Ошибка архитектурного нарушения.

Используется для сигнализации о нарушении архитектурных принципов системы.
"""
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