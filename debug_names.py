import asyncio
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.config import get_config
from core.config.app_config import AppConfig
from core.application_context.application_context import ApplicationContext, ComponentType

async def test():
    config = get_config(profile='prod', data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_discovery(profile='prod', data_dir='data')
    ctx = ApplicationContext(infrastructure_context=infra, config=app_config, profile='prod')
    await ctx.initialize()
    
    services = ctx.components.all_of_type(ComponentType.SERVICE)
    print('All service names:', [s.name for s in services])
    print()
    
    # Check if sql_query_service was in config but not registered
    print('sql_query_service in config:', 'sql_query_service' in app_config.service_configs)
    print()
    
    # Test name resolution
    print('Looking for sql_query_service:')
    print('  with _service:', ctx.components.get(ComponentType.SERVICE, 'sql_query_service'))
    print('  without _service:', ctx.components.get(ComponentType.SERVICE, 'sql_query'))
    print()
    
    # Test action resolution
    action_name = 'sql_query_service.execute'
    parts = action_name.split('.', 1)
    component_name = parts[0]
    normalized = component_name[:-8] if component_name.endswith('_service') else component_name
    print(f'From action "{action_name}":')
    print(f'  component_name: {component_name}')
    print(f'  normalized: {normalized}')
    
    await ctx.shutdown()
    await infra.shutdown()

asyncio.run(test())