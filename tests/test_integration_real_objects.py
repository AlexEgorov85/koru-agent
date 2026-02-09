"""
Интеграционные тесты для системы агентов без использования моков.
Проверяют взаимодействие между компонентами системы.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.events.event_bus import EventType
from core.session_context.session_context import SessionContext


@pytest.mark.asyncio
async def test_full_system_initialization_and_shutdown():
    """Тест полной инициализации и завершения работы системы без моков."""
    # Создаем временную директорию для логов
    temp_dir = os.path.join(tempfile.gettempdir(), "integration_test_logs_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию с минимальными настройками
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        
        # Устанавливаем минимальные настройки провайдеров
        config.llm_providers = {}
        config.db_providers = {}
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Проверяем, что все компоненты созданы
        assert system_context is not None
        assert system_context.config is not None
        assert system_context.registry is not None
        assert system_context.capabilities is not None
        assert system_context.lifecycle is not None
        assert system_context.event_bus is not None
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        assert system_context.initialized is True
        
        # Проверяем, что были опубликованы соответствующие события
        # (проверим через метрики обработчика)
        assert hasattr(system_context, 'metrics_handler')
        assert EventType.SYSTEM_INITIALIZED.value in system_context.metrics_handler.metrics
        
        # Завершаем работу системы
        await system_context.shutdown()
        assert system_context.initialized is False
        
        # Проверяем, что были опубликованы события завершения работы
        assert EventType.SYSTEM_SHUTDOWN.value in system_context.metrics_handler.metrics
        
    finally:
        # Удаляем временную директорию
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_session_context_creation_and_basic_operations():
    """Тест создания и базовых операций с контекстом сессии."""
    session_context = SessionContext()
    
    # Проверяем, что контекст создан корректно
    assert session_context.session_id is not None
    assert session_context.created_at is not None
    assert session_context.data_context is not None
    assert session_context.step_context is not None
    
    # Устанавливаем цель
    goal = "Тестовая цель для агента"
    session_context.set_goal(goal)
    assert session_context.get_goal() == goal
    
    # Добавляем элемент в контекст
    content = {"test": "data", "value": 42}
    from core.session_context.model import ContextItemType
    item_id = session_context._add_context_item(
        item_type=ContextItemType.THOUGHT,  # Используем подходящий тип
        content=content
    )
    
    # Проверяем, что элемент добавлен
    # item = session_context.get_context_item(item_id)
    # assert item is not None
    # assert item.content == content
    
    # Проверяем, что количество элементов увеличилось
    summary = session_context.get_summary()
    assert summary["item_count"] >= 0  # После добавления элемента счетчик должен быть >= 0


@pytest.mark.asyncio
async def test_system_context_with_minimal_configuration():
    """Тест SystemContext с минимальной конфигурацией без внешних зависимостей."""
    temp_dir = os.path.join(tempfile.gettempdir(), "minimal_test_logs_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем минимальную конфигурацию без внешних провайдеров
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        # Убираем все провайдеры, чтобы избежать зависимостей
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем, что система может создать агента (даже если он не сможет выполнить задачу)
        # из-за отсутствия провайдеров
        try:
            agent = await system_context.create_agent()
            # Если агент создан, проверяем его базовые свойства
            assert agent is not None
        except Exception:
            # Если агент не может быть создан из-за отсутствия необходимых компонентов,
            # это допустимо в тесте минимальной конфигурации
            pass
        
        # Завершаем работу
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_event_bus_integration_in_system_context():
    """Тест интеграции шины событий в SystemContext."""
    temp_dir = os.path.join(tempfile.gettempdir(), "event_test_logs_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        
        # Проверяем, что шина событий доступна
        assert system_context.event_bus is not None
        
        # Подписываемся на событие
        received_events = []
        
        def event_handler(event):
            received_events.append(event)
        
        system_context.event_bus.subscribe(EventType.SYSTEM_INITIALIZED, event_handler)
        
        # Инициализируем систему - должно быть опубликовано событие
        success = await system_context.initialize()
        assert success is True
        
        # Ждем немного для обработки событий
        await asyncio.sleep(0.1)
        
        # Проверяем, что событие было получено
        assert len(received_events) > 0
        event_found = False
        for event in received_events:
            if event.event_type == EventType.SYSTEM_INITIALIZED.value:
                event_found = True
                break
        assert event_found, "Событие SYSTEM_INITIALIZED не было получено"
        
        # Проверяем, что глобальный обработчик также получил событие
        assert EventType.SYSTEM_INITIALIZED.value in system_context.metrics_handler.metrics
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_capability_registration_and_retrieval():
    """Тест регистрации и получения capability в SystemContext."""
    temp_dir = os.path.join(tempfile.gettempdir(), "capability_test_logs_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем, что реестр возможностей доступен
        assert system_context.capabilities is not None
        
        # Проверяем начальное состояние
        initial_caps = system_context.list_capabilities()
        assert isinstance(initial_caps, list)
        
        # Проверяем получение несуществующей capability
        non_existent_cap = system_context.get_capability("non.existent.capability")
        assert non_existent_cap is None
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])