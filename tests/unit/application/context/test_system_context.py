#!/usr/bin/env python3
"""
Тестирование новой реализации SystemContext
"""
import asyncio
from application.context.system.system_context import SystemContext
from infrastructure.gateways.event_system import EventSystem
from infrastructure.adapters.event_publisher_adapter import EventPublisherAdapter
from config.models import SystemConfig


async def test_system_context():
    """Тестирование жизненного цикла SystemContext"""
    print("[TEST] Запуск теста SystemContext...")
    
    # Создание конфигурации
    config = SystemConfig(debug=True, log_dir="logs", data_dir="data")
    
    # Создание шины событий
    event_system = EventSystem()
    event_publisher = EventPublisherAdapter(event_system)
    
    # Создание системного контекста
    context = SystemContext(config, event_publisher)
    
    print("[OK] Контекст создан")
    
    # Тест инициализации
    result = await context.initialize()
    assert result == True, 'Инициализация не удалась'
    assert context._initialized == True, 'Флаг инициализации не установлен'
    
    print("[OK] Инициализация прошла успешно")
    
    # Тест получения ресурсов
    file_reader = context.get_resource('file_reader')
    assert file_reader is not None, 'file_reader не найден'
    assert hasattr(file_reader, 'execute'), 'file_reader не имеет метода execute'
    assert file_reader.event_publisher is context._event_publisher, 'Зависимость не инжектирована'
    
    print("[OK] Ресурсы успешно получены")
    
    # Тест получения capability
    # Для этого нам нужно убедиться, что capability зарегистрированы
    capabilities = context.list_capabilities()
    print(f"[INFO] Найдено capability: {len(capabilities)}")
    
    # Тест завершения работы
    await context.shutdown()
    assert context._initialized == False, 'Флаг инициализации не сброшен после shutdown'
    
    print("[OK] Завершение работы прошло успешно")
    
    print("\n[SUCCESS] Все тесты SystemContext пройдены!")


if __name__ == "__main__":
    asyncio.run(test_system_context())
