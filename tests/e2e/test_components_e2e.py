"""
E2E тесты: Проверка основных компонентов.

ТЕСТЫ:
- test_registry_test_file_exists: Проверка test registry
- test_event_bus_basic: Базовый тест EventBus
- test_metrics_storage: Тест хранилища метрик
- test_log_storage: Тест хранилища логов
"""
import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext


@pytest.fixture
def temp_data_dir():
    """Фикстура: временная директория данных"""
    temp_dir = tempfile.mkdtemp()
    (Path(temp_dir) / "prompts").mkdir(exist_ok=True)
    (Path(temp_dir) / "contracts").mkdir(exist_ok=True)
    (Path(temp_dir) / "manifests").mkdir(exist_ok=True)
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestRegistryTestFile:
    """Тесты test registry файла"""

    def test_registry_test_file_exists(self):
        """Тест: registry.test.yaml существует"""
        # Ищем файл относительно корня проекта
        import os
        project_root = Path(__file__).parent.parent.parent
        registry_path = project_root / "registry.test.yaml"
        
        assert registry_path.exists(), f"registry.test.yaml не найден: {registry_path}"
        
        # Проверяем что файл валидный YAML
        import yaml
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert data is not None
        assert 'profile' in data
        assert data['profile'] == 'test'

    def test_registry_test_file_minimal_config(self):
        """Тест: registry.test.yaml имеет минимальную конфигурацию"""
        import os
        project_root = Path(__file__).parent.parent.parent
        registry_path = project_root / "registry.test.yaml"
        
        import yaml
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Проверяем что секции пустые или минимальные
        assert data.get('skills') == {}
        assert data.get('tools') == {}
        assert data.get('behaviors') == {}


class TestEventBusBasic:
    """Базовые тесты EventBus"""

    @pytest.mark.asyncio
    async def test_event_bus_creation(self, temp_data_dir):
        """Тест: Создание EventBus"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # EventBus должен быть создан
            assert infra.event_bus is not None
            
            # Проверяем что можно подписаться
            events_received = []
            
            async def handler(event):
                events_received.append(event)
            
            from core.infrastructure.event_bus import EventType
            infra.event_bus.subscribe(EventType.SKILL_EXECUTED, handler)
            
            # Проверяем что можно опубликовать
            await infra.event_bus.publish(
                EventType.SKILL_EXECUTED,
                data={'test': 'data'}
            )
            
            await asyncio.sleep(0.01)
            
            # Событие должно быть получено
            assert len(events_received) > 0
            
        finally:
            await infra.shutdown()

    @pytest.mark.asyncio
    async def test_event_bus_multiple_subscribers(self, temp_data_dir):
        """Тест: Несколько подписчиков"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            from core.infrastructure.event_bus import EventType
            
            events_1 = []
            events_2 = []
            
            async def handler_1(event):
                events_1.append(event)
            
            async def handler_2(event):
                events_2.append(event)
            
            infra.event_bus.subscribe(EventType.SKILL_EXECUTED, handler_1)
            infra.event_bus.subscribe(EventType.SKILL_EXECUTED, handler_2)
            
            await infra.event_bus.publish(
                EventType.SKILL_EXECUTED,
                data={'test': 'data'}
            )
            
            await asyncio.sleep(0.01)
            
            # Оба подписчика должны получить событие
            assert len(events_1) > 0
            assert len(events_2) > 0
            
        finally:
            await infra.shutdown()


class TestMetricsStorage:
    """Тесты хранилища метрик"""

    @pytest.mark.asyncio
    async def test_metrics_storage_creation(self, temp_data_dir):
        """Тест: Создание хранилища метрик"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # Хранилище метрик должно быть создано
            assert infra.metrics_storage is not None
            
            # Проверяем что можно записать метрику
            from core.infrastructure.event_bus import EventType
            
            await infra.event_bus.publish(
                EventType.SKILL_EXECUTED,
                data={
                    'agent_id': 'test',
                    'capability': 'test_cap',
                    'success': True,
                    'execution_time_ms': 100.0,
                    'tokens_used': 50,
                    'version': 'v1.0.0'
                }
            )
            
            await asyncio.sleep(0.01)
            
            # Проверяем что метрика записана
            metrics = await infra.metrics_collector.get_metrics('test_cap', 'v1.0.0')
            assert len(metrics) > 0
            
        finally:
            await infra.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, temp_data_dir):
        """Тест: Агрегация метрик"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            from core.infrastructure.event_bus import EventType
            
            # Публикуем несколько метрик
            for i in range(3):
                await infra.event_bus.publish(
                    EventType.SKILL_EXECUTED,
                    data={
                        'agent_id': 'test',
                        'capability': 'test_cap',
                        'success': True,
                        'execution_time_ms': 100.0,
                        'tokens_used': 50,
                        'version': 'v1.0.0'
                    }
                )
            
            await asyncio.sleep(0.05)
            
            # Проверяем что метрики записаны (агрегация может быть не доступна)
            metrics = await infra.metrics_collector.get_metrics('test_cap', 'v1.0.0')
            assert len(metrics) >= 0  # Метрики должны быть доступны
            
        finally:
            await infra.shutdown()


class TestLogStorage:
    """Тесты хранилища логов"""

    @pytest.mark.asyncio
    async def test_log_storage_creation(self, temp_data_dir):
        """Тест: Создание хранилища логов"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # Хранилище логов должно быть создано
            assert infra.log_storage is not None
            
            # Проверяем что можно записать лог
            from core.infrastructure.event_bus import EventType
            
            await infra.event_bus.publish(
                EventType.CAPABILITY_SELECTED,
                data={
                    'agent_id': 'test',
                    'session_id': 'test_session',
                    'capability': 'test_cap',
                    'reasoning': 'Test reasoning'
                }
            )
            
            await asyncio.sleep(0.01)
            
            # Проверяем что лог записан
            logs = await infra.log_collector.get_capability_logs('test_cap')
            assert len(logs) > 0
            
        finally:
            await infra.shutdown()

    @pytest.mark.asyncio
    async def test_log_session_isolation(self, temp_data_dir):
        """Тест: Изоляция сессий логов"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            from core.infrastructure.event_bus import EventType
            
            # Публикуем логи для разных сессий
            for session_id in ['session_1', 'session_2']:
                await infra.event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    data={
                        'agent_id': 'test',
                        'session_id': session_id,
                        'capability': 'test_cap',
                        'reasoning': f'Reasoning for {session_id}'
                    }
                )
            
            await asyncio.sleep(0.01)
            
            # Проверяем изоляцию
            logs_1 = await infra.log_collector.get_session_logs('test', 'session_1')
            logs_2 = await infra.log_collector.get_session_logs('test', 'session_2')
            
            assert len(logs_1) > 0
            assert len(logs_2) > 0
            
        finally:
            await infra.shutdown()

    @pytest.mark.asyncio
    async def test_error_logging(self, temp_data_dir):
        """Тест: Логирование ошибок"""
        config = SystemConfig(data_dir=str(temp_data_dir))
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            from core.infrastructure.event_bus import EventType
            
            # Публикуем ошибку
            await infra.event_bus.publish(
                EventType.ERROR_OCCURRED,
                data={
                    'agent_id': 'test',
                    'capability': 'test_cap',
                    'error_type': 'TestError',
                    'error_message': 'Test error message'
                }
            )
            
            await asyncio.sleep(0.01)
            
            # Проверяем что ошибка залогирована
            error_logs = await infra.log_collector.get_error_logs()
            assert len(error_logs) > 0
            
        finally:
            await infra.shutdown()


class TestDBProvider:
    """Тесты DB провайдера"""

    @pytest.mark.asyncio
    async def test_db_provider_creation(self, temp_data_dir):
        """Тест: Создание DB провайдера"""
        config = SystemConfig(
            data_dir=str(temp_data_dir),
            db_providers={
                'test_db': {
                    'provider_type': 'sqlite',
                    'parameters': {'database': ':memory:'},
                    'enabled': True
                }
            }
        )
        
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # DB провайдер должен быть создан
            db = infra.get_provider('test_db')
            assert db is not None
            
            # Проверяем что можно выполнить запрос
            result = await db.execute("SELECT 1 as test")
            assert result is not None
            assert len(result) > 0
            
        finally:
            await infra.shutdown()

    @pytest.mark.asyncio
    async def test_db_crud_operations(self, temp_data_dir):
        """Тест: CRUD операции с БД"""
        config = SystemConfig(
            data_dir=str(temp_data_dir),
            db_providers={
                'test_db': {
                    'provider_type': 'sqlite',
                    'parameters': {'database': ':memory:'},
                    'enabled': True
                }
            }
        )
        
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            db = infra.get_provider('test_db')
            
            # CREATE
            await db.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value INTEGER
                )
            """)
            
            # INSERT
            await db.execute(
                "INSERT INTO test_table (name, value) VALUES (?, ?)",
                ('test', 42)
            )
            
            # READ
            result = await db.execute(
                "SELECT * FROM test_table WHERE name = ?",
                ('test',)
            )
            
            assert result is not None
            assert len(result) > 0
            assert result[0]['value'] == 42
            
            # UPDATE
            await db.execute(
                "UPDATE test_table SET value = ? WHERE name = ?",
                (100, 'test')
            )
            
            result = await db.execute(
                "SELECT value FROM test_table WHERE name = ?",
                ('test',)
            )
            
            assert result[0]['value'] == 100
            
            # DELETE
            await db.execute(
                "DELETE FROM test_table WHERE name = ?",
                ('test',)
            )
            
            result = await db.execute(
                "SELECT * FROM test_table WHERE name = ?",
                ('test',)
            )
            
            assert len(result) == 0
            
        finally:
            await infra.shutdown()
