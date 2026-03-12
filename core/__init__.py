"""
Основные компоненты системы агентов.
"""
# Импорты для событий — теперь из UnifiedEventBus
from .infrastructure.event_bus.unified_event_bus import (
    UnifiedEventBus as EventBus,
    EventType,
    Event,
    get_event_bus
)

__all__ = [
    'EventBus',  # Теперь это UnifiedEventBus
    'EventType',
    'Event',
    'get_event_bus'
]
