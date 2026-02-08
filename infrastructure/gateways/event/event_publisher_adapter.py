
"""
DEPRECATED: This adapter is no longer needed as we now use EventSystem directly.
This file is kept for backward compatibility during migration and will be removed.
"""
import warnings
from domain.abstractions.event_types import Event, EventType, IEventPublisher
from infrastructure.gateways.event_system import EventSystem
from typing import Any, Callable, Awaitable


class EventPublisherAdapter(IEventPublisher):
    """
    DEPRECATED: This adapter is no longer needed as we now use EventSystem directly.
    This class is kept for backward compatibility during migration and will be removed.
    """
    
    def __init__(self, event_system: EventSystem):
        warnings.warn(
            "EventPublisherAdapter is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._event_system = event_system

    async def publish(self, event_type: EventType, source: str, data: Any):
        """
        DEPRECATED: Use EventSystem directly.
        """
        warnings.warn(
            "EventPublisherAdapter.publish is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        event = Event(event_type=event_type, source=source, data=data)
        await self._event_system.publish(event)

    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        DEPRECATED: Use EventSystem directly.
        """
        warnings.warn(
            "EventPublisherAdapter.subscribe is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._event_system.subscribe(event_type, handler)