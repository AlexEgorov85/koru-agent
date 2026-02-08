"""
Unit tests for the simplified EventSystem.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from domain.abstractions.event_types import EventType, Event
from infrastructure.event_system import (
    EventSystem, 
    SecurityEventFilter, 
    SizeLimitFilter, 
    EventValidator, 
    TokenBucketRateLimiter,
    IEventFilter,
    IEventValidator,
    IRateLimiter
)


@pytest.mark.asyncio
async def test_event_system_basic_publish():
    """Test basic event publishing functionality."""
    event_system = EventSystem()
    
    # Create a mock handler
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # Publish an event
    await event_system.publish(EventType.INFO, "test_source", {"key": "value"})
    
    # Verify the handler was called
    handler.assert_called_once()
    args, kwargs = handler.call_args
    event = args[0]
    assert event.event_type == EventType.INFO
    assert event.source == "test_source"
    assert event.data == {"key": "value"}


@pytest.mark.asyncio
async def test_event_system_global_subscription():
    """Test global event subscription."""
    event_system = EventSystem()
    
    # Create a mock handler
    handler = AsyncMock()
    event_system.subscribe_global(handler)
    
    # Publish an event
    await event_system.publish(EventType.WARNING, "test_source", {"key": "value"})
    
    # Verify the handler was called
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_security_event_filter():
    """Test security filter removes sensitive data."""
    event = Event(
        event_type=EventType.INFO,
        source="test_source",
        data={"password": "secret123", "public": "data"}
    )
    
    filter_instance = SecurityEventFilter()
    filtered_event = await filter_instance.filter(event)
    
    assert filtered_event.data["password"] == "***FILTERED***"
    assert filtered_event.data["public"] == "data"


@pytest.mark.asyncio
async def test_size_limit_filter():
    """Test size limit filter drops large events."""
    large_data = {"data": "x" * (1024 * 1024 + 1)}  # 1MB + 1 byte
    event = Event(
        event_type=EventType.INFO,
        source="test_source",
        data=large_data
    )
    
    filter_instance = SizeLimitFilter(max_size_bytes=1024*1024)  # 1MB
    filtered_event = await filter_instance.filter(event)
    
    assert filtered_event is None


@pytest.mark.asyncio
async def test_event_validator():
    """Test event validator."""
    validator = EventValidator()
    
    # Valid event
    valid_event = Event(
        event_type=EventType.INFO,
        source="test_source",
        data={"key": "value"}
    )
    assert await validator.validate(valid_event) is True
    
    # Create an event with a mock that has empty attributes to simulate invalid event
    invalid_event = MagicMock()
    invalid_event.event_type = None
    invalid_event.source = ""
    invalid_event.data = {"key": "value"}
    assert await validator.validate(invalid_event) is False


@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiter functionality."""
    rate_limiter = TokenBucketRateLimiter(
        requests_per_second=1.0,  # 1 request per second
        burst_capacity=1
    )
    
    # First request should be allowed
    assert await rate_limiter.allow_request() is True
    
    # Second request should be denied (rate exceeded)
    assert await rate_limiter.allow_request() is False


@pytest.mark.asyncio
async def test_event_system_with_filters():
    """Test event system with security filter applied."""
    security_filter = SecurityEventFilter()
    event_system = EventSystem(filters=[security_filter])
    
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # Publish event with sensitive data
    await event_system.publish(
        EventType.INFO, 
        "test_source", 
        {"password": "secret123", "public": "data"}
    )
    
    # Verify the handler was called with filtered data
    handler.assert_called_once()
    args, kwargs = handler.call_args
    event = args[0]
    assert event.data["password"] == "***FILTERED***"
    assert event.data["public"] == "data"


@pytest.mark.asyncio
async def test_event_system_with_validators():
    """Test event system with validation."""
    validator = EventValidator()
    event_system = EventSystem(validators=[validator])
    
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # Publish valid event
    await event_system.publish(
        EventType.INFO, 
        "test_source", 
        {"key": "value"}
    )
    
    # Handler should be called for valid event
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_event_system_disabled():
    """Test that disabled event system doesn't publish events."""
    event_system = EventSystem()
    event_system.disable()
    
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # Publish event to disabled system
    await event_system.publish(EventType.INFO, "test_source", {"key": "value"})
    
    # Handler should not be called
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_event_system_with_rate_limiter():
    """Test event system with rate limiting."""
    rate_limiter = TokenBucketRateLimiter(
        requests_per_second=1.0,
        burst_capacity=1
    )
    event_system = EventSystem(rate_limiter=rate_limiter)
    
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # First event should be published
    await event_system.publish(EventType.INFO, "test_source", {"key": "value"})
    assert handler.call_count == 1
    
    # Second event should be rate-limited and not published
    await event_system.publish(EventType.INFO, "test_source", {"key": "value2"})
    # Handler should still only be called once due to rate limiting
    assert handler.call_count == 1


def test_event_system_enable_disable():
    """Test enabling and disabling the event system."""
    event_system = EventSystem()
    
    # Initially enabled
    assert event_system.is_enabled() is True
    
    # Disable
    event_system.disable()
    assert event_system.is_enabled() is False
    
    # Enable
    event_system.enable()
    assert event_system.is_enabled() is True


@pytest.mark.asyncio
async def test_event_system_unsubscribe():
    """Test unsubscribing from events."""
    event_system = EventSystem()
    
    handler = AsyncMock()
    event_system.subscribe(EventType.INFO, handler)
    
    # Publish event - handler should be called
    await event_system.publish(EventType.INFO, "test_source", {"key": "value"})
    assert handler.call_count == 1
    
    # Unsubscribe
    event_system.unsubscribe(EventType.INFO, handler)
    
    # Publish another event - handler should not be called again
    await event_system.publish(EventType.INFO, "test_source", {"key": "value2"})
    assert handler.call_count == 1  # Still 1, not 2


@pytest.mark.asyncio
async def test_event_system_global_unsubscribe():
    """Test unsubscribing from global events."""
    event_system = EventSystem()
    
    handler = AsyncMock()
    event_system.subscribe_global(handler)
    
    # Publish event - handler should be called
    await event_system.publish(EventType.INFO, "test_source", {"key": "value"})
    assert handler.call_count == 1
    
    # Unsubscribe globally
    event_system.unsubscribe_global(handler)
    
    # Publish another event - handler should not be called again
    await event_system.publish(EventType.INFO, "test_source", {"key": "value2"})
    assert handler.call_count == 1  # Still 1, not 2