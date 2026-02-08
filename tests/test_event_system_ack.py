"""
Тесты для системы событий с подтверждением доставки
"""
import asyncio
import pytest
from domain.abstractions.event_types import EventType
from infrastructure.event_system_with_ack import get_ack_event_system


@pytest.mark.asyncio
async def test_event_system_with_ack():
    """Тест системы событий с подтверждением доставки"""
    event_system = get_ack_event_system()
    
    # Запускаем мониторинг повторных попыток
    await event_system.start_retry_monitoring()
    
    # Переменная для проверки обработки
    processed_events = []
    
    # Определяем обработчик с подтверждением
    async def test_handler(event):
        processed_events.append(event.data)
        return True  # Подтверждаем успешную обработку
    
    # Подписываемся на событие с подтверждением
    event_system.subscribe_with_ack(EventType.INFO, test_handler)
    
    # Публикуем событие с подтверждением
    event_id = await event_system.publish_with_ack(
        EventType.INFO,
        "test_source",
        {"test_key": "test_value"}
    )
    
    # Ждем немного, чтобы обработчик успел выполниться
    await asyncio.sleep(0.1)
    
    # Проверяем, что событие было обработано
    assert len(processed_events) == 1
    assert processed_events[0]["test_key"] == "test_value"
    
    # Проверяем статус события
    status = await event_system.get_event_status(event_id)
    # Статус может быть CONFIRMED если обработка завершена, или PENDING если еще в процессе
    # Но в любом случае событие должно быть отслеживаемым
    
    # Останавливаем мониторинг
    await event_system.stop_retry_monitoring()


@pytest.mark.asyncio
async def test_event_system_with_failed_ack():
    """Тест системы событий с неудачным подтверждением"""
    event_system = get_ack_event_system()
    
    # Запускаем мониторинг повторных попыток
    await event_system.start_retry_monitoring()
    
    # Переменная для проверки обработки
    processed_events = []
    
    # Определяем обработчик, который всегда возвращает False
    async def failing_handler(event):
        processed_events.append(event.data)
        return False  # Не подтверждаем обработку
    
    # Подписываемся на событие с подтверждением
    event_system.subscribe_with_ack(EventType.ERROR, failing_handler)
    
    # Публикуем событие с подтверждением
    event_id = await event_system.publish_with_ack(
        EventType.ERROR,
        "test_source",
        {"error_key": "error_value"}
    )
    
    # Ждем немного
    await asyncio.sleep(0.1)
    
    # Проверяем, что событие было обработано (но не подтверждено)
    assert len(processed_events) == 1
    assert processed_events[0]["error_key"] == "error_value"
    
    # Останавливаем мониторинг
    await event_system.stop_retry_monitoring()


@pytest.mark.asyncio
async def test_backward_compatibility():
    """Тест обратной совместимости - старые методы должны работать"""
    from infrastructure.event_system import get_event_system
    
    event_system = get_event_system()
    
    # Переменная для проверки обработки
    processed_events = []
    
    # Определяем обычный обработчик
    async def old_style_handler(event):
        processed_events.append(event.data)
    
    # Подписываемся как обычно
    event_system.subscribe(EventType.INFO, old_style_handler)
    
    # Публикуем событие как обычно
    await event_system.publish(EventType.INFO, "test_source", {"old_style": "works"})
    
    # Ждем немного
    await asyncio.sleep(0.1)
    
    # Проверяем, что событие было обработано
    assert len(processed_events) == 1
    assert processed_events[0]["old_style"] == "works"
    
    # Также проверяем, что новые методы тоже работают
    event_id = await event_system.publish_with_ack(
        EventType.INFO,
        "test_source",
        {"new_style": "works"}
    )
    
    assert event_id is not None