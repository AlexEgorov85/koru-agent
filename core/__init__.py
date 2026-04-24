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

# Версия проекта
from .version import __version__, get_version, get_version_info

__all__ = [
    'EventBus',  # Теперь это UnifiedEventBus
    'EventType',
    'Event',
    'get_event_bus',
    '__version__',
    'get_version',
    'get_version_info',
]
