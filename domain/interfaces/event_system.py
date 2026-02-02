from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable
from enum import Enum
from datetime import datetime


class EventType(Enum):
    """
    Перечисление типов событий.
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    SUCCESS = "success"
    FAILURE = "failure"


class Event:
    """
    Класс события.
    """
    def __init__(self, event_type: EventType, source: str, data: Any, timestamp: datetime = None):
        self.event_type = event_type
        self.source = source
        self.data = data
        self.timestamp = timestamp or datetime.now()
        self.id = f"{event_type.value}_{self.timestamp.timestamp()}_{source}"


class IEventSystem(ABC):
    """Интерфейс для системы событий"""
    
    @abstractmethod
    async def publish(self, event_type: str, source: str, data: Any):
        """Публикация события"""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable):
        """Подписка на событие"""
        pass