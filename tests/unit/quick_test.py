import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from infrastructure.event_system_with_ack import get_ack_event_system
from domain.abstractions.event_types import EventType
import asyncio

async def test():
    event_system = get_ack_event_system()
    await event_system.start_retry_monitoring()
    
    results = []
    async def handler(event):
        results.append(event.data)
        return True
    
    event_system.subscribe_with_ack(EventType.INFO, handler)
    
    event_id = await event_system.publish_with_ack(EventType.INFO, 'test', {'key': 'value'})
    
    # Ждем немного для обработки
    await asyncio.sleep(0.1)
    
    await event_system.stop_retry_monitoring()
    
    assert len(results) == 1
    assert results[0]['key'] == 'value'
    print('SUCCESS: Механизм подтверждения доставки событий работает корректно')

if __name__ == "__main__":
    asyncio.run(test())