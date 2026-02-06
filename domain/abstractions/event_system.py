from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Awaitable
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
    AGENT_THOUGHT = "agent_thought"
    AGENT_ACTION = "agent_action"


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


class IEventPublisher(ABC):
    """Интерфейс издателя событий для инверсии зависимостей."""

    @abstractmethod
    async def publish(self, event_type: EventType, source: str, data: Any):
        """
        Публикация события.
        
        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на событие определенного типа.
        
        Args:
            event_type: Тип события
            handler: Обработчик события
        """
        pass