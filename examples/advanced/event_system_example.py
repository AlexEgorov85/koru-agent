"""
Пример использования системы событий.

Этот пример демонстрирует:
- Создание системы событий
- Подписку на различные типы событий
- Публикацию событий
- Обработку событий
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from domain.abstractions.event_types import EventType, Event
from infrastructure.event_system import EventSystem, SecurityEventFilter, SizeLimitFilter, EventValidator


async def demonstrate_event_system():
    """Демонстрация работы системы событий."""
    print("=== Демонстрация системы событий ===\n")
    
    # Создаем систему событий с фильтрами и валидаторами
    event_system = EventSystem(
        filters=[SecurityEventFilter(), SizeLimitFilter(max_size_bytes=512*1024)],  # 512KB
        validators=[EventValidator()]
    )
    print("✓ Система событий создана с фильтрами и валидаторами")
    
    # Создаем обработчики событий
    received_events = []
    
    async def info_handler(event: Event):
        """Обработчик информационных событий."""
        print(f"  [INFO HANDLER] Получено событие: {event.event_type.value} от {event.source}")
        print(f"  Данные: {event.data}")
        received_events.append(("INFO", event))
    
    async def error_handler(event: Event):
        """Обработчик событий ошибок."""
        print(f"  [ERROR HANDLER] Ошибка: {event.source} - {event.data}")
        received_events.append(("ERROR", event))
    
    async def global_handler(event: Event):
        """Глобальный обработчик всех событий."""
        print(f"  [GLOBAL HANDLER] Событие {event.event_type.value}: {event.data}")
        received_events.append(("GLOBAL", event))
    
    # Подписываемся на события
    event_system.subscribe(EventType.INFO, info_handler)
    event_system.subscribe(EventType.ERROR, error_handler)
    event_system.subscribe_global(global_handler)
    print("✓ Обработчики событий зарегистрированы")
    
    # Публикуем различные события
    print("\n--- Публикация информационного события ---")
    await event_system.publish(
        EventType.INFO,
        "DemoSource",
        {"message": "Это тестовое информационное событие", "timestamp": "2023-01-01T00:00:00Z"}
    )
    
    print("\n--- Публикация события ошибки ---")
    await event_system.publish(
        EventType.ERROR,
        "DemoSource",
        {"error_code": "E001", "message": "Тестовая ошибка", "details": {"component": "test_component"}}
    )
    
    print("\n--- Публикация события прогресса ---")
    await event_system.publish(
        EventType.PROGRESS,
        "TaskProcessor",
        {"task_id": "TASK_001", "progress": 50, "total": 100, "message": "Обработка завершена на 50%"}
    )
    
    print("\n--- Публикация пользовательского события ---")
    await event_system.publish(
        EventType.CUSTOM,
        "CustomComponent",
        {"custom_field": "custom_value", "nested": {"data": [1, 2, 3]}}
    )
    
    # Показываем количество полученных событий
    print(f"\n--- Статистика ---")
    print(f"Всего получено событий: {len(received_events)}")
    
    # Подсчитываем события по типам обработчиков
    info_count = sum(1 for et, _ in received_events if et == "INFO")
    error_count = sum(1 for et, _ in received_events if et == "ERROR")
    global_count = sum(1 for et, _ in received_events if et == "GLOBAL")
    
    print(f"Событий обработано info_handler: {info_count}")
    print(f"Событий обработано error_handler: {error_count}")
    print(f"Событий обработано global_handler: {global_count}")
    
    # Демонстрация фильтрации чувствительных данных
    print(f"\n--- Демонстрация фильтрации чувствительных данных ---")
    await event_system.publish(
        EventType.INFO,
        "SensitiveSource",
        {
            "public_data": "this is public",
            "password": "this should be hidden",
            "api_key": "this should also be hidden",
            "normal_field": "this is fine"
        }
    )
    
    # Добавляем дополнительный фильтр
    print(f"\n--- Добавление дополнительного фильтра ---")
    class CustomFilter:
        async def filter(self, event: Event):
            if hasattr(event, 'data') and isinstance(event.data, dict):
                event.data['filtered_by'] = 'CustomFilter'
            return event
    
    event_system.add_filter(CustomFilter())
    
    await event_system.publish(
        EventType.INFO,
        "FilteredSource",
        {"message": "Сообщение после добавления кастомного фильтра"}
    )
    
    # Проверяем, включена ли система
    print(f"\n--- Состояние системы ---")
    print(f"Система событий включена: {event_system.is_enabled()}")
    
    # Отключаем и пробуем опубликовать событие
    event_system.disable()
    print("Система событий отключена")
    
    await event_system.publish(
        EventType.INFO,
        "DisabledSource",
        {"message": "Это сообщение не должно быть обработано"}
    )
    
    event_system.enable()
    print("Система событий включена снова")
    
    await event_system.publish(
        EventType.INFO,
        "EnabledSource",
        {"message": "Это сообщение должно быть обработано"}
    )
    
    print("\n=== Демонстрация системы событий завершена ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_event_system())