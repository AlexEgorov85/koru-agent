"""
Интеграционные тесты для InfrastructureContext.

ТЕСТЫ:
- test_metrics_publisher_initialized: проверка инициализации MetricsPublisher
- test_full_integration: полный тест сбора метрик
- test_getters: тест методов доступа
- test_shutdown_cleanup: тест корректного завершения работы
- test_event_bus_integration: тест интеграции EventBus
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
    """Интеграционные тесты InfrastructureContext."""

    @pytest.mark.asyncio
    async def test_metrics_publisher_initialized(self, config):
        """Тест инициализации MetricsPublisher."""
        context = InfrastructureContext(config)

        try:
            await context.initialize()
            assert context.metrics_publisher is not None
        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_full_integration(self, config):
        """Полный тест сбора метрик."""
        context = InfrastructureContext(config)

        try:
            await context.initialize()

            assert context.metrics_publisher is not None
            assert context.session_handler is not None

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

            import asyncio
            await asyncio.sleep(0.1)

        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_getters(self, config):
        """Тест методов доступа."""
        context = InfrastructureContext(config)

        try:
            await context.initialize()

            assert context.get_metrics_publisher() is not None
            assert context.get_session_handler() is not None

        finally:
            await context.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, config):
        """Тест корректного завершения работы."""
        context = InfrastructureContext(config)

        await context.initialize()
        assert context.metrics_publisher is not None

        await context.shutdown()

        # Session handler должен быть завершён
        assert context.session_handler is not None

    @pytest.mark.asyncio
    async def test_event_bus_integration(self, config):
        """Тест интеграции EventBus с метриками."""
        context = InfrastructureContext(config)

        try:
            await context.initialize()

            from core.infrastructure.event_bus import EventType

            await context.event_bus.publish(
                EventType.CAPABILITY_SELECTED,
                data={
                    'agent_id': 'test',
                    'capability': 'test.capability',
                    'session_id': 'test'
                }
            )

            await context.event_bus.publish(
                EventType.ERROR_OCCURRED,
                data={
                    'agent_id': 'test',
                    'capability': 'test.capability',
                    'error_type': 'TestError',
                    'session_id': 'test'
                }
            )

            import asyncio
            await asyncio.sleep(0.1)

            assert context.metrics_publisher is not None

        finally:
            await context.shutdown()
