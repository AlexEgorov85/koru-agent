
"""
DEPRECATED: This adapter is no longer needed as we now use EventSystem directly.
This file is kept for backward compatibility during migration and will be removed.
"""
import warnings
from domain.abstractions.event_types import EventType, IEventPublisher
from infrastructure.gateways.event_system import EventSystem as GatewayEventSystem


class EventBusAdapter(IEventPublisher):
    """
    DEPRECATED: This adapter is no longer needed as we now use EventSystem directly.
    This class is kept for backward compatibility during migration and will be removed.
    """
    
    def __init__(self, event_system: GatewayEventSystem):
        warnings.warn(
            "EventBusAdapter is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._event_system = event_system

    async def publish(self, event_type: str, source: str, data: any):
        """
        DEPRECATED: Use EventSystem directly.
        """
        warnings.warn(
            "EventBusAdapter.publish is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        await self._event_system.publish_simple(
            event_type=getattr(EventType, event_type.upper()),
            source=source,
            data=data
        )

    def subscribe(self, event_type: str, handler: callable):
        """
        DEPRECATED: Use EventSystem directly.
        """
        warnings.warn(
            "EventBusAdapter.subscribe is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        self._event_system.subscribe(getattr(EventType, event_type.upper()), handler)