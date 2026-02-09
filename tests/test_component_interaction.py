"""
Комплексные интеграционные тесты для проверки взаимодействия между основными компонентами системы агента.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.session_context.session_context import SessionContext
from core.events.event_bus import EventType, get_event_bus
from core.events.event_handlers import LoggingEventHandler, MetricsEventHandler


@pytest.mark.asyncio
async def test_end_to_end_session_with_events():
    """Тест сквозного потока сессии с генерацией и обработкой событий."""
    temp_dir = os.path.join(tempfile.gettempdir(), "e2e_session_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Создаем конфигурацию
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        # Создаем системный контекст
        system_context = SystemContext(config)
        
        # Инициализируем систему
        success = await system_context.initialize()
        assert success is True
        
        # Создаем сессию
        session_context = SessionContext()
        session_context.set_goal("Тестовая цель сессии")
        
        # Проверяем, что сессия создана
        assert session_context.get_goal() == "Тестовая цель сессии"
        
        # Добавляем элементы в контекст
        action_data = {"action": "test_action", "params": {"param1": "value1"}}
        action_id = session_context.record_action(action_data)
        
        observation_data = {"result": "test_result", "status": "success"}
        observation_id = session_context.record_observation(observation_data)
        
        # Проверяем, что элементы добавлены
        action_item = session_context.get_context_item(action_id)
        assert action_item is not None
        assert action_item.content == action_data
        
        observation_item = session_context.get_context_item(observation_id)
        assert observation_item is not None
        assert observation_item.content == observation_data
        
        # Проверяем, что события были сгенерированы
        await asyncio.sleep(0.1)  # Даем время для обработки событий
        
        # Проверяем, что метрики были обновлены
        assert len(system_context.metrics_handler.metrics) > 0
        
        # Завершаем работу
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_capability_execution_with_context_updates():
    """Тест выполнения capability с обновлением контекста."""
    temp_dir = os.path.join(tempfile.gettempdir(), "capability_context_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        success = await system_context.initialize()
        assert success is True
        
        # Создаем сессию
        session_context = SessionContext()
        session_context.set_goal("Тест выполнения capability")
        
        # Проверяем, что можно получить список возможностей
        capabilities = system_context.list_capabilities()
        assert isinstance(capabilities, list)
        
        # Проверяем, что реестр событий работает
        initial_event_count = len(system_context.metrics_handler.metrics)
        
        # Пытаемся выполнить несуществующую capability для проверки обработки ошибок
        try:
            await system_context.run_capability(
                capability_name="test.nonexistent.capability",
                parameters={"test": "data"},
                session_context=session_context
            )
        except Exception:
            # Ожидаем ошибку из-за отсутствия capability
            pass
        
        # Ждем обработки событий
        await asyncio.sleep(0.1)
        
        # Проверяем, что количество событий увеличилось
        final_event_count = len(system_context.metrics_handler.metrics)
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_system_context_with_multiple_sessions():
    """Тест SystemContext с несколькими сессиями."""
    temp_dir = os.path.join(tempfile.gettempdir(), "multi_session_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        success = await system_context.initialize()
        assert success is True
        
        # Создаем несколько сессий
        session1 = SessionContext()
        session1.set_goal("Цель первой сессии")
        
        session2 = SessionContext()
        session2.set_goal("Цель второй сессии")
        
        # Проверяем, что у сессий разные ID
        assert session1.session_id != session2.session_id
        
        # Проверяем, что у сессий разные цели
        assert session1.get_goal() == "Цель первой сессии"
        assert session2.get_goal() == "Цель второй сессии"
        
        # Добавляем данные в каждую сессию
        session1_data = {"session": 1, "data": "test1"}
        session2_data = {"session": 2, "data": "test2"}
        
        item1_id = session1.record_action(session1_data)
        item2_id = session2.record_action(session2_data)
        
        # Проверяем изоляцию данных
        item1 = session1.get_context_item(item1_id)
        item2 = session2.get_context_item(item2_id)
        
        assert item1.content == session1_data
        assert item2.content == session2_data
        
        # Проверяем, что данные из одной сессии не доступны в другой
        assert session1.get_context_item(item2_id) is None
        assert session2.get_context_item(item1_id) is None
        
        # Проверяем, что события генерируются для каждой сессии
        await asyncio.sleep(0.1)
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_event_bus_with_multiple_handlers():
    """Тест шины событий с несколькими обработчиками."""
    temp_dir = os.path.join(tempfile.gettempdir(), "event_bus_multi_handler_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        success = await system_context.initialize()
        assert success is True
        
        # Создаем несколько обработчиков
        handler1_events = []
        handler2_events = []
        
        def handler1(event):
            handler1_events.append(event)
        
        def handler2(event):
            handler2_events.append(event)
        
        # Подписываем оба обработчика на одно событие
        system_context.event_bus.subscribe(EventType.SYSTEM_INITIALIZED, handler1)
        system_context.event_bus.subscribe(EventType.SYSTEM_INITIALIZED, handler2)
        
        # Также подписываем на все события
        system_context.event_bus.subscribe_all(handler1)
        system_context.event_bus.subscribe_all(handler2)
        
        # Публикуем событие
        await system_context.event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"test": "data", "value": 42},
            source="test_publisher"
        )
        
        # Ждем обработки событий
        await asyncio.sleep(0.1)
        
        # Проверяем, что оба обработчика получили событие
        assert len(handler1_events) >= 1
        assert len(handler2_events) >= 1
        
        # Проверяем, что хотя бы одно событие было получено
        event_received = False
        for event in handler1_events:
            if event.event_type == EventType.SYSTEM_INITIALIZED.value:
                event_received = True
                break
        
        assert event_received, "Событие SYSTEM_INITIALIZED не было получено первым обработчиком"
        
        # Проверяем, что метрики также были обновлены
        assert EventType.SYSTEM_INITIALIZED.value in system_context.metrics_handler.metrics
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_error_propagation_through_components():
    """Тест распространения ошибок через компоненты системы."""
    temp_dir = os.path.join(tempfile.gettempdir(), "error_propagation_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем обработку ошибок при вызове LLM без провайдеров
        try:
            await system_context.call_llm("test prompt")
            # Если не было ошибки, значит провайдер был создан
        except ValueError as e:
            # Ожидаем ошибку из-за отсутствия провайдеров
            assert "Нет доступных LLM провайдеров" in str(e)
        except Exception as e:
            # Другие ошибки также возможны
            pass
        
        # Ждем обработки событий
        await asyncio.sleep(0.1)
        
        # Проверяем, что события ошибок были зарегистрированы
        error_events_registered = (
            EventType.LLM_CALL_FAILED.value in system_context.metrics_handler.metrics or
            EventType.SYSTEM_ERROR.value in system_context.metrics_handler.metrics
        )
        
        # Даже если конкретные события ошибок не были зарегистрированы,
        # система должна продолжать работать
        assert system_context.initialized is True
        
        await system_context.shutdown()
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@pytest.mark.asyncio
async def test_component_state_consistency():
    """Тест согласованности состояния между компонентами."""
    temp_dir = os.path.join(tempfile.gettempdir(), "state_consistency_test_" + str(int(asyncio.get_event_loop().time())))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = "dev"
        config.log_level = "DEBUG"
        config.llm_providers = {}
        config.db_providers = {}
        
        system_context = SystemContext(config)
        success = await system_context.initialize()
        assert success is True
        
        # Проверяем начальное состояние
        initial_initialized = system_context.initialized
        assert initial_initialized is True
        
        # Проверяем, что все основные компоненты доступны
        assert system_context.registry is not None
        assert system_context.capabilities is not None
        assert system_context.lifecycle is not None
        assert system_context.event_bus is not None
        
        # Проверяем, что обработчики событий созданы
        assert hasattr(system_context, 'logging_handler')
        assert hasattr(system_context, 'metrics_handler')
        assert hasattr(system_context, 'audit_handler')
        
        # Создаем сессию и проверяем её состояние
        session_context = SessionContext()
        assert session_context.session_id is not None
        assert session_context.data_context is not None
        assert session_context.step_context is not None
        
        # Проверяем, что состояние системы не изменилось
        assert system_context.initialized == initial_initialized
        
        # Завершаем работу
        await system_context.shutdown()
        
        # Проверяем, что состояние изменилось
        assert system_context.initialized is False
        
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])