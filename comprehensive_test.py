#!/usr/bin/env python3
"""
Комплексное тестирование новой реализации SystemContext
"""
import asyncio
from application.context.system.system_context import SystemContext
from application.gateways.execution.execution_gateway import ExecutionGateway
from infrastructure.gateways.event_system import EventSystem
from infrastructure.adapters.event_publisher_adapter import EventPublisherAdapter
from config.models import SystemConfig


async def test_comprehensive_functionality():
    """Комплексное тестирование функциональности SystemContext"""
    print("[TEST] Запуск комплексного теста SystemContext...")
    
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
    capabilities = context.list_capabilities()
    print(f"[INFO] Найдено capability: {len(capabilities)}")
    
    # Тест получения шины событий
    event_bus = context.get_event_bus()
    assert event_bus is not None, 'Шина событий не найдена'
    assert event_bus is event_publisher, 'Шина событий не совпадает с ожидаемой'
    
    print("[OK] Шина событий успешно получена")
    
    # Тест ExecutionGateway
    execution_gateway = ExecutionGateway(context)
    assert execution_gateway is not None, 'ExecutionGateway не создан'
    assert execution_gateway._system_context is context, 'Контекст не инжектирован в ExecutionGateway'
    
    print("[OK] ExecutionGateway успешно создан")
    
    # Тест завершения работы
    await context.shutdown()
    assert context._initialized == False, 'Флаг инициализации не сброшен после shutdown'
    
    print("[OK] Завершение работы прошло успешно")
    
    print("\n[SUCCESS] Все комплексные тесты SystemContext пройдены!")


def test_architectural_purity():
    """Тестирование архитектурной чистоты"""
    print("\n[TEST] Проверка архитектурной чистоты...")
    
    # Проверка, что домен не зависит от инфраструктуры
    import subprocess
    import sys
    
    # Проверка с помощью поиска в файлах
    import os
    
    # Проверим, что в домене нет импортов инфраструктуры
    domain_dir = "domain"
    infrastructure_import_found = False
    
    for root, dirs, files in os.walk(domain_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if "from infrastructure" in content or "import infrastructure" in content:
                        infrastructure_import_found = True
                        print(f"[ERROR] Найден импорт инфраструктуры в домене: {filepath}")
    
    assert not infrastructure_import_found, "Обнаружены импорты инфраструктуры в домене"
    
    # Проверим, что домен не зависит от application
    application_import_found = False
    for root, dirs, files in os.walk(domain_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if "from application" in content or "import application" in content:
                        application_import_found = True
                        print(f"[ERROR] Найден импорт application в домене: {filepath}")
    
    assert not application_import_found, "Обнаружены импорты application в домене"
    
    print("[OK] Архитектурная чистота подтверждена")


if __name__ == "__main__":
    asyncio.run(test_comprehensive_functionality())
    test_architectural_purity()