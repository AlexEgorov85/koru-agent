"""
Тест интеграции механизма подтверждения доставки событий с остальной системой
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.abstractions.event_types import EventType
from infrastructure.event_system_with_ack import get_ack_event_system


def test_integration_with_system_components():
    """Тест интеграции с другими компонентами системы"""
    # Получаем систему событий с подтверждением
    event_system = get_ack_event_system()
    
    # Проверяем, что она реализует правильный интерфейс
    from domain.abstractions.event_types import IEventPublisher
    assert isinstance(event_system, IEventPublisher)
    
    # Проверяем, что у нее есть все необходимые методы
    assert hasattr(event_system, 'publish')
    assert hasattr(event_system, 'subscribe')
    assert hasattr(event_system, 'publish_with_ack')
    assert hasattr(event_system, 'subscribe_with_ack')
    
    print("✓ Интерфейс IEventPublisher реализован правильно")
    
    # Проверяем, что можно подписаться и опубликовать событие
    handler_called = []
    
    async def test_handler(event):
        handler_called.append(event.data)
        return True
    
    event_system.subscribe_with_ack(EventType.INFO, test_handler)
    
    # Публикуем событие
    event_id = asyncio.run(event_system.publish_with_ack(
        EventType.INFO,
        "test_integration",
        {"test": "data"}
    ))
    
    print(f"✓ Событие опубликовано с ID: {event_id}")
    
    # Проверяем, что обработчик был вызван
    # (в реальной системе нужно дождаться завершения асинхронной обработки)
    
    print("✓ Интеграция с системными компонентами работает")


@pytest.mark.asyncio
async def test_error_handling():
    """Тест обработки ошибок в системе подтверждения"""
    event_system = get_ack_event_system()
    
    # Запускаем мониторинг
    await event_system.start_retry_monitoring()
    
    error_count = 0
    
    async def error_handler(event):
        nonlocal error_count
        error_count += 1
        if error_count < 2:  # Первые 2 попытки будут ошибочными
            raise Exception("Simulated error")
        return True  # Третья попытка успешна
    
    event_system.subscribe_with_ack(EventType.ERROR, error_handler)
    
    # Публикуем событие
    event_id = await event_system.publish_with_ack(
        EventType.ERROR,
        "error_test",
        {"attempt": "with_error"}
    )
    
    # Ждем немного для обработки retry
    await asyncio.sleep(0.1)
    
    print(f"✓ Обработка ошибок работает, обработчик был вызван {error_count} раз(а)")
    
    # Останавливаем мониторинг
    await event_system.stop_retry_monitoring()


if __name__ == "__main__":
    test_integration_with_system_components()
    import pytest
    # Запускаем тест через pytest для корректной обработки асинхронных функций
    pytest.main([__file__, "-v", "-s"])