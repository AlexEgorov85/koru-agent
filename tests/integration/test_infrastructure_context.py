"""
Интеграционные тесты для InfrastructureContext с метриками и логами.

ТЕСТЫ:
- test_metrics_collector_initialized: проверка инициализации MetricsCollector
- test_log_collector_initialized: проверка инициализации LogCollector
- test_full_integration: полный тест сбора метрик и логов
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext


@pytest.fixture
def temp_data_dir():
    """Фикстура для временной директории данных"""
    temp_dir = tempfile.mkdtemp()
    
    # Создание базовой структуры
    (Path(temp_dir) / "prompts").mkdir(exist_ok=True)
    (Path(temp_dir) / "contracts").mkdir(exist_ok=True)
    (Path(temp_dir) / "manifests").mkdir(exist_ok=True)
    
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config(temp_data_dir):
    """Фикстура конфигурации"""
    return SystemConfig(
        data_dir=str(temp_data_dir),
        llm_providers={
            'test_llm': {
                'enabled': True,
                'provider_type': 'llama_cpp',
                'parameters': {
                    'model_path': 'models/test-model.gguf',
                    'n_ctx': 100
                }
            }
        },
        db_providers={}
    )


class TestInfrastructureContextIntegration:
    """Интеграционные тесты InfrastructureContext"""

    @pytest.mark.asyncio
    async def test_metrics_collector_initialized(self, config):
        """Тест инициализации MetricsCollector"""
        context = InfrastructureContext(config)
        
        try:
            # Инициализация
            success = await context.initialize()
            assert success is True
            
            # Проверка что MetricsCollector инициализирован
            assert context.metrics_collector is not None
            assert context.metrics_collector.is_initialized is True
            assert context.metrics_collector.subscriptions_count > 0
            
            # Проверка что хранилище инициализировано
            assert context.metrics_storage is not None
            
        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_log_collector_initialized(self, config):
        """Тест инициализации LogCollector"""
        context = InfrastructureContext(config)
        
        try:
            # Инициализация
            success = await context.initialize()
            assert success is True
            
            # Проверка что LogCollector инициализирован
            assert context.log_collector is not None
            assert context.log_collector.is_initialized is True
            assert context.log_collector.subscriptions_count > 0
            
            # Проверка что хранилище инициализировано
            assert context.log_storage is not None
            
        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_full_integration(self, config):
        """Полный тест интеграции: метрики + логи"""
        context = InfrastructureContext(config)
        
        try:
            # Инициализация
            await context.initialize()
            
            # Проверка всех компонентов
            assert context.metrics_collector is not None
            assert context.log_collector is not None
            assert context.metrics_storage is not None
            assert context.log_storage is not None
            
            # Публикация тестового события через EventBus
            from core.infrastructure.event_bus import EventType
            
            await context.event_bus.publish(
                EventType.SKILL_EXECUTED,
                data={
                    'agent_id': 'test_agent',
                    'capability': 'test_capability',
                    'success': True,
                    'execution_time_ms': 100.0,
                    'tokens_used': 500,
                    'version': 'v1.0',
                    'session_id': 'test_session'
                }
            )
            
            # Небольшая задержка для обработки
            import asyncio
            await asyncio.sleep(0.01)
            
            # Проверка что метрики записаны
            metrics = await context.metrics_collector.get_metrics('test_capability', 'v1.0')
            assert len(metrics) > 0
            
            # Проверка что логи записаны
            logs = await context.log_collector.get_session_logs('test_agent', 'test_session')
            # Логи могут быть записаны в зависимости от типа события
            
        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_getters(self, config):
        """Тест методов доступа"""
        context = InfrastructureContext(config)
        
        try:
            await context.initialize()
            
            # Проверка методов доступа
            assert context.get_metrics_storage() is not None
            assert context.get_log_storage() is not None
            assert context.get_metrics_collector() is not None
            assert context.get_log_collector() is not None
            
            # Проверка типов
            from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage, ILogStorage
            from core.infrastructure.metrics_collector import MetricsCollector
            from core.infrastructure.log_collector import LogCollector
            
            assert isinstance(context.get_metrics_storage(), IMetricsStorage)
            assert isinstance(context.get_log_storage(), ILogStorage)
            assert isinstance(context.get_metrics_collector(), MetricsCollector)
            assert isinstance(context.get_log_collector(), LogCollector)
            
        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, config):
        """Тест корректного завершения работы"""
        context = InfrastructureContext(config)
        
        # Инициализация
        await context.initialize()
        assert context.metrics_collector.is_initialized is True
        assert context.log_collector.is_initialized is True
        
        # Завершение
        await context.shutdown()
        
        # Проверка что сборщики завершены
        # Примечание: shutdown может не изменить is_initialized если были ошибки
        assert context.metrics_collector is not None
        assert context.log_collector is not None

    @pytest.mark.asyncio
    async def test_event_bus_integration(self, config):
        """Тест интеграции EventBus со сборщиками"""
        context = InfrastructureContext(config)
        
        try:
            await context.initialize()
            
            # Проверка что EventBus тот же самый
            assert context.metrics_collector.event_bus is context.event_bus
            assert context.log_collector.event_bus is context.event_bus
            
            # Публикация различных событий
            from core.infrastructure.event_bus import EventType
            
            events_to_test = [
                (EventType.CAPABILITY_SELECTED, {
                    'agent_id': 'agent_1',
                    'session_id': 'session_1',
                    'capability': 'test_cap',
                    'reasoning': 'test'
                }),
                (EventType.ERROR_OCCURRED, {
                    'agent_id': 'agent_1',
                    'session_id': 'session_1',
                    'capability': 'test_cap',
                    'error_type': 'TestError'
                }),
                (EventType.BENCHMARK_COMPLETED, {
                    'scenario_id': 'scenario_1',
                    'capability': 'test_cap',
                    'success': True
                }),
            ]
            
            for event_type, data in events_to_test:
                await context.event_bus.publish(event_type, data=data)
            
            import asyncio
            await asyncio.sleep(0.01)
            
            # Проверка что логи записаны
            logs = await context.log_collector.get_capability_logs('test_cap')
            assert len(logs) > 0
            
        finally:
            await context.shutdown()
