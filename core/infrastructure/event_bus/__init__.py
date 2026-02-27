"""
Инициализация модуля событий.

АРХИТЕКТУРА:
- event_bus: базовый класс EventBus
- domain_event_bus: менеджер доменных шин (рекомендуется)
- event_handlers: обработчики событий
"""
from .event_bus import EventBus, EventType, Event
from .domain_event_bus import (
    EventBusManager,
    DomainEventBus,
    DomainEvent,
    EventDomain,
    EVENT_TYPE_TO_DOMAIN,
    get_event_bus_manager,
    get_event_bus,
    reset_event_bus_manager,
)
from .event_handlers import MetricsEventHandler, AuditEventHandler, DebuggingEventHandler

__all__ = [
    # Базовые классы
    'EventBus',
    'EventType',
    'Event',

    # Доменные шины (рекомендуется)
    'EventBusManager',
    'DomainEventBus',
    'DomainEvent',
    'EventDomain',
    'EVENT_TYPE_TO_DOMAIN',
    'get_event_bus_manager',
    'get_event_bus',
    'reset_event_bus_manager',
    
    # Обработчики
    'MetricsEventHandler',
    'AuditEventHandler',
    'DebuggingEventHandler',
]