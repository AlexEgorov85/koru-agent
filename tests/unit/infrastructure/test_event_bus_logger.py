"""
Тесты для EventBusLogger.

TESTS:
- test_info_sync: Синхронное INFO логирование
- test_debug_sync: Синхронное DEBUG логирование
- test_warning_sync: Синхронное WARNING логирование
- test_error_sync: Синхронное ERROR логирование
- test_fifo_order: FIFO порядок событий
"""
import pytest
import asyncio

from core.infrastructure.event_bus.unified_event_bus import (
    create_event_bus,
    EventType,
)
from core.infrastructure.logging.logger import EventBusLogger


@pytest.fixture
async def event_bus():
    """Фикстура: новая шина для каждого теста."""
    bus = create_event_bus()
    yield bus
    await bus.shutdown(timeout=5.0)


@pytest.fixture
def logger(event_bus):
    """Фикстура: логгер для тестов."""
    return EventBusLogger(
        event_bus,
        session_id="test_session",
        agent_id="test_agent",
        component="TestLogger"
    )


class TestEventBusLoggerSync:
    """Тесты синхронных методов EventBusLogger."""

    @pytest.mark.asyncio
    async def test_info_sync(self, event_bus, logger):
        """Синхронное INFO логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование
        logger.info_sync("Test info message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test info message"
        assert events[0].data["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_debug_sync(self, event_bus, logger):
        """Синхронное DEBUG логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_DEBUG, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование
        logger.debug_sync("Test debug message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test debug message"
        assert events[0].data["level"] == "DEBUG"

    @pytest.mark.asyncio
    async def test_warning_sync(self, event_bus, logger):
        """Синхронное WARNING логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_WARNING, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование
        logger.warning_sync("Test warning message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test warning message"
        assert events[0].data["level"] == "WARNING"

    @pytest.mark.asyncio
    async def test_error_sync(self, event_bus, logger):
        """Синхронное ERROR логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_ERROR, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование
        logger.error_sync("Test error message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test error message"
        assert events[0].data["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_fifo_order(self, event_bus, logger):
        """FIFO порядок синхронных событий."""
        events = []

        def handler(e):
            events.append(e.data.get("seq"))

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Серия синхронных логов
        for i in range(5):
            logger.info_sync(f"Message {i}", seq=i)

        await asyncio.sleep(0.1)

        # События должны прийти в порядке FIFO
        assert events == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_info_sync_with_args(self, event_bus, logger):
        """Синхронное логирование с аргументами."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование с форматированием
        logger.info_sync("Test %s message", "info")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test info message"

    @pytest.mark.asyncio
    async def test_info_sync_with_extra_data(self, event_bus, logger):
        """Синхронное логирование с дополнительными данными."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Синхронное логирование с extra данными
        logger.info_sync("Test message", custom_field="custom_value")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["custom_field"] == "custom_value"

    @pytest.mark.asyncio
    async def test_sync_before_worker_created(self, event_bus, logger):
        """Синхронное логирование до создания worker."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Синхронное логирование без созданного worker
        logger.info_sync("Test message before worker")
        await asyncio.sleep(0.05)

        # Событие не должно быть обработано (worker не создан)
        assert len(events) == 0


class TestEventBusLoggerAsync:
    """Тесты асинхронных методов EventBusLogger."""

    @pytest.mark.asyncio
    async def test_info_async(self, event_bus, logger):
        """Асинхронное INFO логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Асинхронное логирование
        await logger.info("Test async info message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test async info message"
        assert events[0].data["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_mixed_sync_async(self, event_bus, logger):
        """Смешанное синхронное и асинхронное логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)

        # Асинхронный лог
        await logger.info("Async message 1")
        # Синхронный лог
        logger.info_sync("Sync message 2")
        # Асинхронный лог
        await logger.info("Async message 3")
        # Синхронный лог
        logger.info_sync("Sync message 4")

        await asyncio.sleep(0.1)

        # Все сообщения должны быть обработаны
        assert len(events) == 4
        messages = [e.data["message"] for e in events]
        assert "Async message 1" in messages
        assert "Sync message 2" in messages
        assert "Async message 3" in messages
        assert "Sync message 4" in messages
