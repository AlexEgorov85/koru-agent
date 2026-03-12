"""
Инициализация модуля событий.

АРХИТЕКТУРА:
- unified_event_bus: единая шина с session isolation + domain routing
- event_handlers: обработчики событий
"""
from .unified_event_bus import (
    UnifiedEventBus,
    Event,
    EventType,
    EventDomain,
    EVENT_TYPE_TO_DOMAIN,
    get_event_domain,
    get_event_bus,
    create_event_bus,
    shutdown_event_bus,
)
from .event_handlers import MetricsEventHandler, AuditEventHandler, DebuggingEventHandler

__all__ = [
    # === ЕДИНАЯ ШИНА ===
    'UnifiedEventBus',
    'Event',
    'EventType',
    'EventDomain',
    'EVENT_TYPE_TO_DOMAIN',
    'get_event_domain',
    'get_event_bus',  # Основной singleton
    'create_event_bus',
    'shutdown_event_bus',

    # Обработчики
    'MetricsEventHandler',
    'AuditEventHandler',
    'DebuggingEventHandler',
]
