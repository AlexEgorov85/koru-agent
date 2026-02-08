"""
Event filters for the simplified event system.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
import json
from datetime import datetime

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


class SecurityEventFilter(IEventFilter):
    """Filter to remove sensitive data from events."""
    
    def __init__(self, sensitive_fields=None):
        self.sensitive_fields = sensitive_fields or [
            "password", "token", "api_key", "secret", "credentials",
            "private_key", "certificate", "oauth_token", "auth_token"
        ]
    
    async def filter(self, event: Event) -> Optional[Event]:
        """Remove sensitive data from event data."""
        if not hasattr(event, 'data') or not isinstance(event.data, dict):
            return event
        
        filtered_data = event.data.copy()
        
        for field in self.sensitive_fields:
            if field in filtered_data:
                filtered_data[field] = "***FILTERED***"
        
        # Create a new event with filtered data
        filtered_event = Event(
            event_type=event.event_type,
            source=event.source,
            data=filtered_data,
            timestamp=event.timestamp
        )
        return filtered_event


class SizeLimitFilter(IEventFilter):
    """Filter to limit event size."""
    
    def __init__(self, max_size_bytes: int = 1024 * 1024):  # 1MB default
        self.max_size_bytes = max_size_bytes
    
    async def filter(self, event: Event) -> Optional[Event]:
        """Check if event size is within limits."""
        try:
            event_json = json.dumps(str(event.data))
            if len(event_json.encode('utf-8')) > self.max_size_bytes:
                logging.warning(f"Dropping event due to size limit: {event.id}")
                return None
        except Exception:
            logging.warning(f"Could not serialize event data for size check: {event.id}")
            return None
        
        return event