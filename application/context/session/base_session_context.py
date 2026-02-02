# Базовый интерфейс контекста сессии
"""
BaseSessionContext(ABC) — контракт контекста сессии
"""

from abc import ABC, abstractmethod


class BaseSessionContext(ABC):
    """
    Абстрактный базовый класс для контекста сессии
    """
    
    @abstractmethod
    def initialize(self):
        """
        Инициализировать контекст сессии
        """
        pass
    
    @abstractmethod
    def update_state(self, state_data):
        """
        Обновить состояние сессии
        
        Args:
            state_data: Данные для обновления состояния
        """
        pass
    
    @abstractmethod
    def get_state(self):
        """
        Получить текущее состояние сессии
        
        Returns:
            Текущее состояние сессии
        """
        pass