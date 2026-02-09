"""
Тесты для шины событий.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from core.events.event_bus import EventBus, EventType, Event, get_event_bus
from core.events.event_handlers import LoggingEventHandler, MetricsEventHandler, AuditEventHandler


@pytest.fixture
def event_bus():
    """Фикстура для шины событий."""
    bus = EventBus()
    yield bus


@pytest.mark.asyncio
async def test_event_bus_creation(event_bus):
    """Тест создания шины событий."""
    assert event_bus is not None
    assert len(event_bus._subscribers) == 0
    assert len(event_bus._all_subscribers) == 0


@pytest.mark.asyncio
async def test_subscribe_and_publish(event_bus):
    """Тест подписки и публикации событий."""
    # Создаем mock-функцию для обработки события
    handler = AsyncMock()
    
    # Подписываемся на событие
    event_bus.subscribe(EventType.AGENT_CREATED, handler)
    
    # Публикуем событие
    event_data = {"agent_id": "test_agent", "type": "test"}
    await event_bus.publish(EventType.AGENT_CREATED, event_data, source="test_source")
    
    # Проверяем, что обработчик был вызван
    await asyncio.sleep(0.01)  # Даем время для асинхронного выполнения
    handler.assert_called_once()
    
    # Проверяем, что переданный объект события содержит правильные данные
    called_event = handler.call_args[0][0]
    assert called_event.event_type == EventType.AGENT_CREATED.value
    assert called_event.data == event_data
    assert called_event.source == "test_source"


@pytest.mark.asyncio
async def test_subscribe_all_events(event_bus):
    """Тест подписки на все события."""
    handler = AsyncMock()
    
    # Подписываемся на все события
    event_bus.subscribe_all(handler)
    
    # Публикуем несколько разных событий
    await event_bus.publish(EventType.AGENT_CREATED, {"agent_id": "test1"})
    await event_bus.publish(EventType.SYSTEM_INITIALIZED, {"system_id": "test2"})
    
    # Ждем выполнения
    await asyncio.sleep(0.01)
    
    # Проверяем, что обработчик был вызван дважды
    assert handler.call_count == 2


@pytest.mark.asyncio
async def test_event_bus_with_handlers():
    """Тест шины событий с реальными обработчиками."""
    event_bus = get_event_bus()  # Используем глобальную шину
    
    # Создаем обработчики
    logging_handler = LoggingEventHandler(log_dir="tests/logs")
    metrics_handler = MetricsEventHandler()
    audit_handler = AuditEventHandler(audit_log_dir="tests/logs/audit")
    
    # Подписываем обработчики
    event_bus.subscribe(EventType.AGENT_CREATED, logging_handler.handle_event)
    event_bus.subscribe(EventType.AGENT_CREATED, metrics_handler.handle_event)
    event_bus.subscribe(EventType.AGENT_CREATED, audit_handler.handle_event)
    
    # Публикуем событие
    await event_bus.publish(
        EventType.AGENT_CREATED,
        data={"agent_id": "test_agent", "capabilities": ["test"]},
        source="test_module"
    )
    
    # Ждем выполнения
    await asyncio.sleep(0.01)
    
    # Проверяем, что метрики были обновлены
    assert EventType.AGENT_CREATED.value in metrics_handler.metrics
    assert metrics_handler.metrics[EventType.AGENT_CREATED.value] >= 1


@pytest.mark.asyncio
async def test_event_bus_error_handling():
    """Тест обработки ошибок в обработчиках событий."""
    event_bus = EventBus()
    
    # Создаем обработчик, который выбрасывает исключение
    def error_handler(event):
        raise ValueError("Test error in handler")
    
    # Подписываемся на событие
    event_bus.subscribe(EventType.SYSTEM_ERROR, error_handler)
    
    # Публикуем событие - не должно быть исключения в вызывающем коде
    await event_bus.publish(EventType.SYSTEM_ERROR, {"error": "test"})
    
    # Ждем выполнения
    await asyncio.sleep(0.01)
    
    # Проверяем, что публикация прошла без ошибок (обработчик внутри обернут в try-catch)
    # Если мы дошли до этой точки, то исключения не было в основном потоке


@pytest.mark.asyncio
async def test_event_bus_unsubscribe(event_bus):
    """Тест отписки от событий."""
    handler = AsyncMock()
    
    # Подписываемся на событие
    event_bus.subscribe(EventType.AGENT_CREATED, handler)
    
    # Публикуем событие - обработчик должен сработать
    await event_bus.publish(EventType.AGENT_CREATED, {"test": "data1"})
    await asyncio.sleep(0.01)
    assert handler.call_count == 1
    
    # Отписываемся от события
    event_bus.unsubscribe(EventType.AGENT_CREATED, handler)
    
    # Публикуем событие снова - обработчик не должен сработать
    await event_bus.publish(EventType.AGENT_CREATED, {"test": "data2"})
    await asyncio.sleep(0.01)
    # Количество вызовов должно остаться прежним
    assert handler.call_count == 1


def test_event_creation():
    """Тест создания события."""
    event_data = {"key": "value"}
    event = Event(
        event_type=EventType.AGENT_CREATED.value,
        data=event_data,
        source="test_source",
        correlation_id="test_corr_id"
    )
    
    assert event.event_type == EventType.AGENT_CREATED.value
    assert event.data == event_data
    assert event.source == "test_source"
    assert event.correlation_id == "test_corr_id"
    assert event.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__])