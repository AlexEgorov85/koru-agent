import asyncio
from core.agent.factory import AgentFactory
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig
from core.config import get_config
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.models.enums.common_enums import ComponentType

async def main():
    config = get_config(profile='prod', data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_discovery(
        profile='prod',
        data_dir='data',
        discovery=infra.resource_discovery
    )
    app_ctx = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    await app_ctx.initialize()
    
    registry = app_ctx.components
    
    # List all services
    all_services = registry.all_of_type(ComponentType.SERVICE)
    print('=== ALL SERVICES ===')
    for svc in all_services:
        name = getattr(svc, 'name', 'unknown')
        print(f'  - {name}')
    
    # Check sql_generation - try different names
    for name in ['sql_generation', 'sql_generation_service', 'SQLGeneration']:
        sql_svc = registry.get(ComponentType.SERVICE, name)
        if sql_svc:
            print(f'=== SQL_GENERATION (as {name}) ===')
            print(f'Exists: True')
            print(f'prompts keys: {list(sql_svc.prompts.keys()) if hasattr(sql_svc, "prompts") else "NO ATTR"}')
            print(f'is_initialized: {sql_svc.is_initialized if hasattr(sql_svc, "is_initialized") else "N/A"}')
            break
    
    await app_ctx.shutdown()
    await infra.shutdown()

if __name__ == '__main__':
    asyncio.run(main())