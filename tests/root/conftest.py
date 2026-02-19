"""
Shared fixtures for root tests.
"""
import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ApplicationContext


@pytest.fixture(scope="function")
async def infra():
    """Create InfrastructureContext for tests."""
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra_context = InfrastructureContext(system_config)
    await infra_context.initialize()
    yield infra_context
    await infra_context.shutdown()


@pytest.fixture(scope="function")
async def app_context(infra):
    """Create ApplicationContext with registry config."""
    app_config = AppConfig.from_registry(profile="prod", registry_path="registry.yaml")
    
    context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod",
        use_data_repository=True
    )
    
    await context.initialize()
    yield context
    
    # Cleanup
    context._initialized = False


@pytest.fixture
def tools(app_context):
    """Get all tools from app_context."""
    from core.application.context.application_context import ComponentType
    return app_context.components.all_of_type(ComponentType.TOOL)
