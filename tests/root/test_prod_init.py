import asyncio
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_prod_initialization():
    config = SystemConfig(data_dir='.')
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_registry(profile='prod')
    app_context = ApplicationContext(infra, app_config, profile='prod')
    
    success = await app_context.initialize()
    
    print(f'Production initialization success: {success}')
    if app_context.data_repository:
        print(f'Manifests loaded: {len(app_context.data_repository._manifest_cache)}')
    
    await infra.shutdown()

asyncio.run(test_prod_initialization())