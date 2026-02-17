import asyncio
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_prod_initialization():
    # Используем правильный путь к данным - директорию data/
    config = SystemConfig(data_dir='data')
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    # Загружаем конфигурацию из реестра
    app_config = AppConfig.from_registry(profile='prod')
    
    print(f"Skills in config: {list(app_config.skill_configs.keys())}")
    print(f"Services in config: {list(app_config.service_configs.keys())}")
    print(f"Tools in config: {list(app_config.tool_configs.keys())}")
    print(f"Behaviors in config: {list(app_config.behavior_configs.keys())}")
    
    app_context = ApplicationContext(infra, app_config, profile='prod')
    
    success = await app_context.initialize()
    
    print(f'Production initialization success: {success}')
    if app_context.data_repository:
        print(f'Manifests loaded: {len(app_context.data_repository._manifest_cache)}')
    
    await infra.shutdown()

asyncio.run(test_prod_initialization())