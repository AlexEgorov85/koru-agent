"""
Инициализация модуля событий.

АРХИТЕКТУРА:
- event_bus: базовый класс EventBus (для обратной совместимости)
- domain_event_bus: менеджер доменных шин (новое, рекомендуется)
- event_handlers: обработчики событий
"""
from .event_bus import EventBus, EventType, Event, get_event_bus as get_legacy_event_bus
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
    # Базовые классы (обратная совместимость)
    'EventBus',
    'EventType',
    'Event',
    'get_legacy_event_bus',
    
    # Доменные шины (новое, рекомендуется)
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