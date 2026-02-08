"""
Event filters for the simplified event system.
"""

from abc import ABC, abstractmethod
from typing import Optional
from domain.abstractions.event_types import Event


class IEventFilter(ABC):
    """Interface for event filters."""
    
    @abstractmethod
    async def filter(self, event: Event) -> Optional[Event]:
        """
        Filter an event.
        
        Args:
            event: The event to filter
            
        Returns:
            The filtered event or None if the event should be dropped
        """
        pass