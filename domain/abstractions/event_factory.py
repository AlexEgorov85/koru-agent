"""
Абстракции для создания системных компонентов (инверсия зависимостей)
"""
from abc import ABC, abstractmethod
from typing import Protocol
from domain.abstractions.event_types import IEventPublisher


class IEventPublisherFactory(ABC):
    """Фабрика для создания издателей событий"""
    
    @abstractmethod
    def create_event_publisher(self) -> IEventPublisher:
        """
        Создать новый экземпляр издателя событий
        
        Returns:
            IEventPublisher: Новый экземпляр издателя событий
        """
        pass

    @abstractmethod
    def get_global_event_publisher(self) -> IEventPublisher:
        """
        Получить глобальный экземпляр издателя событий (синглтон)
        
        Returns:
            IEventPublisher: Глобальный экземпляр издателя событий
        """
        pass