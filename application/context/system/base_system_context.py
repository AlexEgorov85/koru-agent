# Базовый интерфейс системного контекста
"""
BaseSystemContext(ABC) — контракт системного контекста
"""

from abc import ABC, abstractmethod


class BaseSystemContext(ABC):
    """
    Абстрактный базовый класс для системного контекста
    """
    
    @abstractmethod
    def initialize_resources(self):
        """
        Инициализировать системные ресурсы
        """
        pass
    
    @abstractmethod
    def manage_resources(self):
        """
        Управлять системными ресурсами
        """
        pass
    
    @abstractmethod
    def get_system_state(self):
        """
        Получить состояние системного контекста
        
        Returns:
            Состояние системного контекста
        """
        pass