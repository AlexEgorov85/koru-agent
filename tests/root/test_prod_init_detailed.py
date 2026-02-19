"""Тесты инициализации ApplicationContext в production режиме."""
import asyncio
import pytest
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.fixture
async def infra_context():
    """Создание InfrastructureContext для тестов."""
    config = SystemConfig(data_dir='.')
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.mark.asyncio
async def test_prod_initialization(infra_context):
    """Проверка инициализации в production режиме."""
    app_config = AppConfig.from_registry(profile='prod')

    app_context = ApplicationContext(infra_context, app_config, profile='prod')
    success = await app_context.initialize()

    assert success, "Production initialization should succeed"
    assert app_context.data_repository is not None, "DataRepository should be initialized"


@pytest.mark.asyncio
async def test_prod_config_components(infra_context):
    """Проверка наличия компонентов в конфигурации."""
    app_config = AppConfig.from_registry(profile='prod')

    assert len(app_config.skill_configs) > 0, "Should have skill configs"
    assert len(app_config.service_configs) > 0, "Should have service configs"
    assert len(app_config.tool_configs) > 0, "Should have tool configs"
    assert len(app_config.behavior_configs) > 0, "Should have behavior configs"


@pytest.mark.asyncio
async def test_prod_manifests_loaded(infra_context):
    """Проверка загрузки манифестов."""
    app_config = AppConfig.from_registry(profile='prod')
    app_context = ApplicationContext(infra_context, app_config, profile='prod')

    await app_context.initialize()

    manifests_count = len(app_context.data_repository._manifest_cache)
    assert manifests_count > 0, "Should load manifests from data directory"