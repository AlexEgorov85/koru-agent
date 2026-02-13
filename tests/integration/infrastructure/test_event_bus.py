"""
Интеграционные тесты для EventBus.

Тестирует:
- Подписку и публикацию событий
- Обработку асинхронных и синхронных обработчиков
- Корректную фильтрацию по типу событий
- Изоляцию событий через correlation_id
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_basic_subscription_and_publish():
    """
    Интеграционный тест: базовая подписка и публикация событий
    """
    bus = EventBus()
    
    # Создаем обработчик события
    received_events = []
    
    async def event_handler(event: Event):
        received_events.append(event)
    
    # Подписываемся на событие
    bus.subscribe(EventType.AGENT_CREATED, event_handler)
    
    # Публикуем событие
    await bus.publish(EventType.AGENT_CREATED, data={"agent_id": "test-agent"})
    
    # Проверяем, что событие было получено
    await asyncio.sleep(0.01)  # короткая задержка для обработки асинхронных задач
    assert len(received_events) == 1
    assert received_events[0].event_type == EventType.AGENT_CREATED.value
    assert received_events[0].data["agent_id"] == "test-agent"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_subscribe_all_events():
    """
    Интеграционный тест: подписка на все события
    """
    bus = EventBus()
    
    # Создаем обработчики
    specific_events = []
    all_events = []
    
    async def specific_handler(event: Event):
        specific_events.append(event)
    
    async def all_handler(event: Event):
        all_events.append(event)
    
    # Подписываемся на конкретное событие и на все события
    bus.subscribe(EventType.AGENT_CREATED, specific_handler)
    bus.subscribe_all(all_handler)
    
    # Публикуем событие
    await bus.publish(EventType.AGENT_CREATED, data={"agent_id": "test-agent"})
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что событие получено обеими подписками
    assert len(specific_events) == 1
    assert len(all_events) == 1
    assert specific_events[0].event_type == EventType.AGENT_CREATED.value
    assert all_events[0].event_type == EventType.AGENT_CREATED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_synchronous_handler():
    """
    Интеграционный тест: обработка синхронных обработчиков
    """
    bus = EventBus()
    
    # Создаем синхронный обработчик
    received_events = []
    
    def sync_handler(event: Event):
        received_events.append(event)
    
    # Подписываемся на событие
    bus.subscribe(EventType.SYSTEM_INITIALIZED, sync_handler)
    
    # Публикуем событие
    await bus.publish(EventType.SYSTEM_INITIALIZED, data={"status": "ready"})
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что событие было получено
    assert len(received_events) == 1
    assert received_events[0].event_type == EventType.SYSTEM_INITIALIZED.value
    assert received_events[0].data["status"] == "ready"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers():
    """
    Интеграционный тест: несколько подписчиков на одно событие
    """
    bus = EventBus()
    
    # Создаем несколько обработчиков
    handler1_events = []
    handler2_events = []
    handler3_events = []
    
    async def handler1(event: Event):
        handler1_events.append(event)
    
    async def handler2(event: Event):
        handler2_events.append(event)
    
    def handler3(event: Event):
        handler3_events.append(event)
    
    # Подписываемся несколькими обработчиками
    bus.subscribe(EventType.AGENT_COMPLETED, handler1)
    bus.subscribe(EventType.AGENT_COMPLETED, handler2)
    bus.subscribe(EventType.AGENT_COMPLETED, handler3)
    
    # Публикуем событие
    await bus.publish(EventType.AGENT_COMPLETED, data={"result": "success"})
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что событие получено всеми подписчиками
    assert len(handler1_events) == 1
    assert len(handler2_events) == 1
    assert len(handler3_events) == 1
    
    for events in [handler1_events, handler2_events, handler3_events]:
        assert events[0].event_type == EventType.AGENT_COMPLETED.value
        assert events[0].data["result"] == "success"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    """
    Интеграционный тест: отписка от событий
    """
    bus = EventBus()
    
    received_events = []
    
    async def event_handler(event: Event):
        received_events.append(event)
    
    # Подписываемся
    bus.subscribe(EventType.AGENT_FAILED, event_handler)
    
    # Публикуем событие - должно быть получено
    await bus.publish(EventType.AGENT_FAILED, data={"error": "test-error"})
    await asyncio.sleep(0.01)
    
    assert len(received_events) == 1
    
    # Отписываемся
    bus.unsubscribe(EventType.AGENT_FAILED, event_handler)
    
    # Публикуем событие снова - не должно быть получено
    await bus.publish(EventType.AGENT_FAILED, data={"error": "another-error"})
    await asyncio.sleep(0.01)
    
    # Количество событий не должно измениться
    assert len(received_events) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_event_filtering():
    """
    Интеграционный тест: фильтрация событий по типу
    """
    bus = EventBus()
    
    agent_events = []
    system_events = []
    
    async def agent_handler(event: Event):
        agent_events.append(event)
    
    async def system_handler(event: Event):
        system_events.append(event)
    
    # Подписываемся на разные типы событий
    bus.subscribe(EventType.AGENT_CREATED, agent_handler)
    bus.subscribe(EventType.SYSTEM_INITIALIZED, system_handler)
    
    # Публикуем разные события
    await bus.publish(EventType.AGENT_CREATED, data={"agent_id": "agent1"})
    await bus.publish(EventType.SYSTEM_INITIALIZED, data={"status": "ready"})
    await bus.publish(EventType.AGENT_COMPLETED, data={"result": "done"})  # не должен быть получен
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что события получены только соответствующими обработчиками
    assert len(agent_events) == 1
    assert len(system_events) == 1
    assert agent_events[0].event_type == EventType.AGENT_CREATED.value
    assert system_events[0].event_type == EventType.SYSTEM_INITIALIZED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_exception_handling():
    """
    Интеграционный тест: обработка исключений в обработчиках
    """
    bus = EventBus()
    
    successful_events = []
    
    async def failing_handler(event: Event):
        raise Exception("Test exception in handler")
    
    async def successful_handler(event: Event):
        successful_events.append(event)
    
    # Подписываемся на событие с обработчиками, один из которых будет падать
    bus.subscribe(EventType.ERROR_OCCURRED, failing_handler)
    bus.subscribe(EventType.ERROR_OCCURRED, successful_handler)
    
    # Публикуем событие - должно быть получено успешным обработчиком, 
    # несмотря на то, что один из обработчиков падает
    await bus.publish(EventType.ERROR_OCCURRED, data={"info": "test"})
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что успешный обработчик получил событие
    assert len(successful_events) == 1
    assert successful_events[0].event_type == EventType.ERROR_OCCURRED.value
    assert successful_events[0].data["info"] == "test"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_with_correlation_id():
    """
    Интеграционный тест: использование correlation_id для изоляции событий
    """
    bus = EventBus()
    
    correlation_events = []
    
    async def correlation_handler(event: Event):
        correlation_events.append(event)
    
    # Подписываемся на событие
    bus.subscribe(EventType.STEP_REGISTERED, correlation_handler)
    
    # Публикуем событие с correlation_id
    await bus.publish(
        EventType.STEP_REGISTERED, 
        data={"step": "initial"},
        correlation_id="correlation-123"
    )
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что событие получено с правильным correlation_id
    assert len(correlation_events) == 1
    assert correlation_events[0].correlation_id == "correlation-123"
    assert correlation_events[0].data["step"] == "initial"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_direct_event_object():
    """
    Интеграционный тест: публикация готового объекта Event
    """
    bus = EventBus()
    
    received_events = []
    
    async def event_handler(event: Event):
        received_events.append(event)
    
    bus.subscribe(EventType.METRIC_COLLECTED, event_handler)
    
    # Создаем и публикуем готовый объект Event
    event_obj = Event(
        event_type=EventType.METRIC_COLLECTED.value,
        data={"metric": "response_time", "value": 123.45},
        source="test_source",
        correlation_id="test_corr_id"
    )
    
    await bus.publish(event_obj)
    
    # Ждем обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что событие получено полностью
    assert len(received_events) == 1
    assert received_events[0].event_type == EventType.METRIC_COLLECTED.value
    assert received_events[0].data["metric"] == "response_time"
    assert received_events[0].data["value"] == 123.45
    assert received_events[0].source == "test_source"
    assert received_events[0].correlation_id == "test_corr_id"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_subscriber_count():
    """
    Интеграционный тест: проверка количества подписчиков
    """
    bus = EventBus()
    
    async def handler1(event: Event):
        pass
    
    async def handler2(event: Event):
        pass
    
    # Проверяем начальное количество подписчиков
    assert bus.get_subscribers_count(EventType.SERVICE_REGISTERED) == 0
    
    # Подписываемся
    bus.subscribe(EventType.SERVICE_REGISTERED, handler1)
    assert bus.get_subscribers_count(EventType.SERVICE_REGISTERED) == 1
    
    bus.subscribe(EventType.SERVICE_REGISTERED, handler2)
    assert bus.get_subscribers_count(EventType.SERVICE_REGISTERED) == 2
    
    # Отписываемся
    bus.unsubscribe(EventType.SERVICE_REGISTERED, handler1)
    assert bus.get_subscribers_count(EventType.SERVICE_REGISTERED) == 1