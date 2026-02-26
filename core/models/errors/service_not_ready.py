"""
Custom exception for when a service is not ready to be accessed.
"""
class ServiceNotReadyError(Exception):
    """
    Исключение, возникающее когда сервис запрашивается до завершения его инициализации.
    
    ATTRIBUTES:
    - message: описание ошибки
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)