
from domain.abstractions.event_types import EventType, IEventPublisher
from infrastructure.gateways.event_system import EventSystem as GatewayEventSystem


class EventBusAdapter(IEventPublisher):
    def __init__(self, event_system: GatewayEventSystem):  # EventSystem из gateways
        self._event_system = event_system
    
    async def publish(self, event_type: str, source: str, data: any):
        await self._event_system.publish_simple(
            event_type=getattr(EventType, event_type.upper()),
            source=source,
            data=data
        )
    
    def subscribe(self, event_type: str, handler: callable):
        self._event_system.subscribe(getattr(EventType, event_type.upper()), handler)