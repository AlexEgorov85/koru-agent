#!/usr/bin/env python3
"""
Интеграционное тестирование всех компонентов SystemContext
"""
import asyncio
from application.context.system.system_context import SystemContext
from application.gateways.execution.execution_gateway import ExecutionGateway
from infrastructure.gateways.event_system import EventSystem
from infrastructure.adapters.event_publisher_adapter import EventPublisherAdapter
from config.models import SystemConfig
from domain.abstractions.event_system import EventType


async def test_integration():
    """Тестирование интеграции всех компонентов"""
    print("[INTEGRATION TEST] Запуск интеграционного теста...")
    
    # Создание конфигурации
    config = SystemConfig(
        debug=True, 
        log_dir="logs", 
        data_dir="data",
        llm_providers={
            "test_llm": {
                "type_provider": "llama_cpp",
                "model_name": "qwen-4b",
                "parameters": {},
                "enabled": True,
                "fallback_providers": []
            }
        },
        db_providers={}
    )
    
    # Создание шины событий
    event_system = EventSystem()
    event_publisher = EventPublisherAdapter(event_system)
    
    # Создание системного контекста
    context = SystemContext(config, event_publisher)
    
    print("[STEP 1] Контекст создан")
    
    # Подпишемся на события для проверки работы шины
    received_events = []
    
    async def event_collector(event):
        received_events.append(event)
    
    event_publisher.subscribe(EventType.INFO, event_collector)
    event_publisher.subscribe(EventType.ERROR, event_collector)
    event_publisher.subscribe(EventType.WARNING, event_collector)
    
    print("[STEP 2] Подписка на события выполнена")
    
    # Тест инициализации
    result = await context.initialize()
    assert result == True, 'Инициализация не удалась'
    assert context._initialized == True, 'Флаг инициализации не установлен'
    
    print("[STEP 3] Инициализация прошла успешно")
    
    # Тест получения ресурсов
    file_reader = context.get_resource('file_reader')
    assert file_reader is not None, 'file_reader не найден'
    assert hasattr(file_reader, 'execute'), 'file_reader не имеет метода execute'
    print("[STEP 4] Ресурсы успешно получены")
    
    # Тест получения capability
    capabilities = context.list_capabilities()
    print(f"[STEP 5] Найдено capability: {len(capabilities)}")
    
    # Тест получения шины событий
    event_bus = context.get_event_bus()
    assert event_bus is not None, 'Шина событий не найдена'
    print("[STEP 6] Шина событий успешно получена")
    
    # Тест ExecutionGateway
    execution_gateway = ExecutionGateway(context)
    assert execution_gateway is not None, 'ExecutionGateway не создан'
    print("[STEP 7] ExecutionGateway успешно создан")
    
    # Тест публикации события
    await event_publisher.publish(
        EventType.INFO,
        "IntegrationTest",
        {"message": "Тестовое сообщение для проверки шины событий"}
    )
    print("[STEP 8] Публикация события выполнена")
    
    # Проверка, что событие было получено
    await asyncio.sleep(0.1)  # Небольшая пауза для обработки события
    assert len(received_events) >= 1, "Событие не было получено подписчиком"
    print(f"[STEP 9] Получено событий: {len(received_events)}")
    
    # Тест завершения работы
    await context.shutdown()
    assert context._initialized == False, 'Флаг инициализации не сброшен после shutdown'
    print("[STEP 10] Завершение работы прошло успешно")
    
    print(f"\n[SUCCESS] Интеграционный тест пройден! Получено {len(received_events)} событий.")


def test_architectural_boundaries():
    """Тестирование архитектурных границ"""
    print("\n[BOUNDARY TEST] Проверка архитектурных границ...")
    
    # Проверим, что домен не содержит импортов инфраструктуры и application
    import os
    
    domain_path = "domain"
    violations = []
    
    for root, dirs, files in os.walk(domain_path):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Проверяем наличие нежелательных импортов
                    if "from infrastructure" in content or "import infrastructure" in content:
                        if not "__pycache__" in filepath:  # Исключаем кэш-файлы
                            violations.append(f"Infrastructure import in domain: {filepath}")
                    
                    if "from application" in content or "import application" in content:
                        if not "__pycache__" in filepath:  # Исключаем кэш-файлы
                            violations.append(f"Application import in domain: {filepath}")
    
    if violations:
        for violation in violations:
            print(f"[ERROR] {violation}")
        raise AssertionError(f"Найдены нарушения архитектурных границ: {len(violations)}")
    else:
        print("[SUCCESS] Архитектурные границы соблюдены")


if __name__ == "__main__":
    asyncio.run(test_integration())
    test_architectural_boundaries()
    print("\n[SUCCESS] Все интеграционные тесты пройдены успешно!")
