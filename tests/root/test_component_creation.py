"""Тесты создания компонентов ApplicationContext."""
import asyncio
import pytest
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig, ComponentType


@pytest.fixture
async def infra_context():
    """Создание InfrastructureContext для тестов."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.mark.asyncio
async def test_prompt_service_component_creation(infra_context):
    """Проверка создания и регистрации prompt_service компонента."""
    app_config = AppConfig(config_id="test")
    app_config.service_configs = {
        "prompt_service": ComponentConfig(
            variant_id="prompt_service_default",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )
    }

    app_context = ApplicationContext(infra_context, app_config, profile='prod')
    component_configs = app_context._resolve_component_configs()

    assert "prompt_service" in component_configs[ComponentType.SERVICE], \
        "Prompt service config should be in resolved component configs"

    success = await app_context.initialize()
    assert success, "ApplicationContext initialization should succeed"

    prompt_service = app_context.components.get(ComponentType.SERVICE, "prompt_service")
    assert prompt_service is not None, "Prompt service should be registered"
    assert prompt_service.name == "prompt_service", "Prompt service name should match"