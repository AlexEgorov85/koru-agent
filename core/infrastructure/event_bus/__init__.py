"""
Инициализация модуля событий.

АРХИТЕКТУРА:
- event_bus: базовый класс EventBus (legacy)
- event_bus_concurrent: конкурентная шина с сессиями (legacy)
- domain_event_bus: менеджер доменных шин (legacy)
- unified_event_bus: единая шина с session isolation + domain routing (рекомендуется)
- event_bus_adapter: адаптер для обратной совместимости (временный)
"""
from .event_bus import EventBus, EventType, Event
from .event_bus_concurrent import (
    EventBus as EventBusConcurrent,
    get_event_bus as get_concurrent_event_bus,
    create_event_bus as create_concurrent_event_bus,
)
from .domain_event_bus import (
    EventBusManager,
    DomainEventBus,
    DomainEvent,
    EventDomain,
    EVENT_TYPE_TO_DOMAIN,
    get_event_bus_manager,
    get_event_bus as get_legacy_event_bus,
    reset_event_bus_manager,
)
from .unified_event_bus import (
    UnifiedEventBus,
    Event as UnifiedEvent,
    EventType as UnifiedEventType,
    EventDomain as UnifiedEventDomain,
    get_event_domain,
    get_event_bus,
    create_event_bus,
    shutdown_event_bus,
)
from .event_bus_adapter import (
    EventBusAdapter,
    DomainEventBusProxy,
    get_event_bus_adapter,
    reset_event_bus_adapter,
)
from .event_handlers import MetricsEventHandler, AuditEventHandler, DebuggingEventHandler

__all__ = [
    # Базовые классы (legacy)
    'EventBus',
    'EventType',
    'Event',

    # Конкурентная шина (legacy)
    'EventBusConcurrent',
    'get_concurrent_event_bus',
    'create_concurrent_event_bus',

    # Доменные шины (legacy, рекомендуется миграция на UnifiedEventBus)
    'EventBusManager',
    'DomainEventBus',
    'DomainEvent',
    'EventDomain',
    'EVENT_TYPE_TO_DOMAIN',
    'get_event_bus_manager',
    'get_legacy_event_bus',
    'reset_event_bus_manager',

    # === НОВАЯ ЕДИНАЯ ШИНА (рекомендуется) ===
    'UnifiedEventBus',
    'UnifiedEvent',
    'UnifiedEventType',
    'UnifiedEventDomain',
    'get_event_domain',
    'get_event_bus',  # Новый singleton
    'create_event_bus',
    'shutdown_event_bus',

    # Адаптер для обратной совместимости (временный)
    'EventBusAdapter',
    'DomainEventBusProxy',
    'get_event_bus_adapter',
    'reset_event_bus_adapter',

    # Обработчики
    'MetricsEventHandler',
    'AuditEventHandler',
    'DebuggingEventHandler',
]
