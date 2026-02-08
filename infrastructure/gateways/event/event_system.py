"""
DEPRECATED: This is the old EventSystem implementation. 
Use the new simplified EventSystem from infrastructure.event_system instead.
This file is kept for backward compatibility during migration and will be removed.
"""

import warnings
from typing import Any, Dict, List, Callable, Awaitable
import logging

from domain.abstractions.event_types import Event, EventType, IEventPublisher
# Import the new simplified EventSystem
from infrastructure.event_system import EventSystem as NewEventSystem


class EventSystem(IEventPublisher):
    """
    DEPRECATED: This is the old EventSystem implementation. 
    Use the new simplified EventSystem from infrastructure.event_system instead.
    This class is kept for backward compatibility during migration and will be removed.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Old EventSystem is deprecated. Use infrastructure.event_system.EventSystem instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Create an instance of the new EventSystem with default configuration
        self._new_system = NewEventSystem()
        
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.subscribe is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.subscribe(event_type, handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.unsubscribe is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.unsubscribe(event_type, handler)

    def subscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.subscribe_global is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.subscribe_global(handler)

    def unsubscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.unsubscribe_global is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.unsubscribe_global(handler)

    async def publish(self, event_type: EventType, source: str, data: Any) -> None:
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.publish is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        await self._new_system.publish(event_type, source, data)

    def enable(self):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.enable is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.enable()

    def disable(self):
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.disable is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_system.disable()

    def is_enabled(self) -> bool:
        """
        DEPRECATED: Use new EventSystem directly.
        """
        warnings.warn(
            "Old EventSystem.is_enabled is deprecated. Use new EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        return self._new_system.is_enabled()


# For backward compatibility, create a global instance
event_system = EventSystem()


def get_event_system() -> EventSystem:
    """
    DEPRECATED: Use new EventSystem directly.
    """
    warnings.warn(
        "get_event_system() is deprecated. Use new EventSystem directly.",
        DeprecationWarning,
        stacklevel=2
    )
    return event_system