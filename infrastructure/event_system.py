"""
Simplified EventSystem with composition-based filters and validators.
This replaces the complex multi-layered abstraction with a single clean implementation.
"""

from typing import Any, Dict, List, Callable, Awaitable, Optional
import logging
from datetime import datetime
from abc import ABC, abstractmethod

from domain.abstractions.event_types import Event, EventType, IEventPublisher


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


class IEventValidator(ABC):
    """Interface for event validators."""
    
    @abstractmethod
    async def validate(self, event: Event) -> bool:
        """
        Validate an event.
        
        Args:
            event: The event to validate
            
        Returns:
            True if the event is valid, False otherwise
        """
        pass


class IRateLimiter(ABC):
    """Interface for rate limiting."""
    
    @abstractmethod
    async def allow_request(self) -> bool:
        """
        Check if a request is allowed based on rate limits.
        
        Returns:
            True if the request is allowed, False otherwise
        """
        pass


class SecurityEventFilter(IEventFilter):
    """Filter to remove sensitive data from events."""
    
    def __init__(self, sensitive_fields: Optional[List[str]] = None):
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
        import json
        try:
            event_json = json.dumps(str(event.data))
            if len(event_json.encode('utf-8')) > self.max_size_bytes:
                logging.warning(f"Dropping event due to size limit: {event.id}")
                return None
        except Exception:
            logging.warning(f"Could not serialize event data for size check: {event.id}")
            return None
        
        return event


class EventValidator(IEventValidator):
    """Basic event validator."""
    
    async def validate(self, event: Event) -> bool:
        """Validate that the event has required properties."""
        if not event.event_type:
            return False
        if not event.source:
            return False
        return True


class TokenBucketRateLimiter(IRateLimiter):
    """Token bucket rate limiter implementation."""
    
    def __init__(self, requests_per_second: float, burst_capacity: int):
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.tokens = burst_capacity
        self.last_refill_time = datetime.now()
    
    async def allow_request(self) -> bool:
        """Check if a request is allowed based on rate limits."""
        current_time = datetime.now()
        time_passed = (current_time - self.last_refill_time).total_seconds()
        
        # Refill tokens based on time passed
        tokens_to_add = time_passed * self.requests_per_second
        self.tokens = min(self.burst_capacity, self.tokens + tokens_to_add)
        self.last_refill_time = current_time
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        else:
            return False


class EventSystem(IEventPublisher):
    """
    Simplified event system with composition-based filtering and validation.

    This replaces the complex multi-layered abstraction with a single clean implementation
    that supports pluggable filters, validators, and rate limiters through composition.
    """

    def __init__(
        self,
        filters: Optional[List[IEventFilter]] = None,
        validators: Optional[List[IEventValidator]] = None,
        rate_limiter: Optional[IRateLimiter] = None
    ):
        """Initialize the event system with optional filters, validators, and rate limiter."""
        self._handlers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        self._global_handlers: List[Callable[[Event], Awaitable[None]]] = []
        self._filters = filters or []
        self._validators = validators or []
        self._rate_limiter = rate_limiter
        self._enabled = True
        self._logger = logging.getLogger(__name__)
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call when event occurs
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Unsubscribe from events of a specific type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def subscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Subscribe to all events.
        
        Args:
            handler: Handler function to call for all events
        """
        if handler not in self._global_handlers:
            self._global_handlers.append(handler)
    
    def unsubscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Unsubscribe from all events.
        
        Args:
            handler: Handler function to remove from global subscription
        """
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)
    
    async def _validate_event(self, event: Event) -> bool:
        """Validate an event against all registered validators."""
        for validator in self._validators:
            if not await validator.validate(event):
                return False
        return True
    
    async def _filter_event(self, event: Event) -> Optional[Event]:
        """Apply all registered filters to an event."""
        filtered_event = event
        for event_filter in self._filters:
            filtered_event = await event_filter.filter(filtered_event)
            if filtered_event is None:
                return None
        return filtered_event
    
    async def publish(self, event_type: EventType, source: str, data: Any) -> None:
        """
        Publish an event after applying validation, filtering, and rate limiting.
        
        Args:
            event_type: Type of the event
            source: Source of the event
            data: Data associated with the event
        """
        if not self._enabled:
            return
        
        # Create the event
        event = Event(event_type=event_type, source=source, data=data)
        
        # Apply rate limiting if configured
        if self._rate_limiter:
            if not await self._rate_limiter.allow_request():
                self._logger.warning(f"Event dropped due to rate limiting: {event.id}")
                return
        
        # Validate the event
        if not await self._validate_event(event):
            self._logger.warning(f"Event validation failed: {event.id}")
            return
        
        # Apply filters
        filtered_event = await self._filter_event(event)
        if filtered_event is None:
            self._logger.info(f"Event filtered out: {event.id}")
            return
        
        # Publish the event
        await self._publish_event_internal(filtered_event)
    
    async def _publish_event_internal(self, event: Event) -> None:
        """Internal method to publish an event to subscribers."""
        try:
            # Call global handlers
            for handler in self._global_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error(f"Error in global event handler: {e}", exc_info=True)
            
            # Call specific type handlers
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error(f"Error in event handler for {event.event_type}: {e}", exc_info=True)
        except Exception as e:
            self._logger.error(f"Error publishing event: {e}", exc_info=True)
    
    def enable(self):
        """Enable the event system."""
        self._enabled = True
    
    def disable(self):
        """Disable the event system."""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if the event system is enabled."""
        return self._enabled
    
    def add_filter(self, event_filter: IEventFilter):
        """Add a filter to the event system."""
        if event_filter not in self._filters:
            self._filters.append(event_filter)
    
    def remove_filter(self, event_filter: IEventFilter):
        """Remove a filter from the event system."""
        if event_filter in self._filters:
            self._filters.remove(event_filter)
    
    def add_validator(self, validator: IEventValidator):
        """Add a validator to the event system."""
        if validator not in self._validators:
            self._validators.append(validator)
    
    def remove_validator(self, validator: IEventValidator):
        """Remove a validator from the event system."""
        if validator in self._validators:
            self._validators.remove(validator)

    # Методы для подтверждения доставки событий (реализация по умолчанию - пустые)
    async def publish_with_ack(self, event_type: EventType, source: str, data: Any) -> str:
        """
        Публикация события с отслеживанием подтверждения (реализация по умолчанию)
        
        Returns:
            str: ID события
        """
        # Вызываем обычную публикацию и возвращаем ID
        event = Event(event_type=event_type, source=source, data=data)
        await self.publish(event_type, source, data)
        return event.id

    def subscribe_with_ack(self, event_type: EventType, handler: Callable[[Event], Awaitable[bool]]):
        """
        Подписка на событие с подтверждением (реализация по умолчанию)
        """
        # Оборачиваем обработчик для совместимости
        async def wrapped_handler(event: Event) -> None:
            try:
                await handler(event)
            except Exception as e:
                self._logger.error(f"Error in handler: {e}", exc_info=True)
        
        self.subscribe(event_type, wrapped_handler)


# Global instance for backward compatibility during migration
event_system = EventSystem(
    filters=[SecurityEventFilter(), SizeLimitFilter()],
    validators=[EventValidator()],
    rate_limiter=TokenBucketRateLimiter(requests_per_second=100.0, burst_capacity=200)
)


def get_event_system() -> EventSystem:
    """
    Get the global event system instance.

    Returns:
        EventSystem: The global event system instance
    """
    return event_system