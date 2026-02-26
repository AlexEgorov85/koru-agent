"""
Custom exceptions for structured output functionality.
"""


class StructuredOutputError(Exception):
    """
    Исключение для ошибок структурированного вывода.
    
    ATTRIBUTES:
    - message: описание ошибки
    - model_name: имя модели, для которой произошла ошибка
    - attempts: список попыток с деталями ошибок
    - correlation_id: ID корреляции для трассировки
    """
    def __init__(self, message: str, model_name: str, attempts: list, correlation_id: str):
        self.message = message
        self.model_name = model_name
        self.attempts = attempts
        self.correlation_id = correlation_id
        super().__init__(self.message)