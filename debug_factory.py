import asyncio
import traceback
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
    
    # Try to create just the sql_query_service component
    print('Attempting to create sql_query_service...')
    try:
        from core.components.action_executor import ActionExecutor
        executor = ActionExecutor(ctx)
        component = await ctx._create_component(
            ComponentType.SERVICE,
            'sql_query_service',
            app_config.service_configs['sql_query_service'],
            executor
        )
        print(f'Created: {component}')
        print(f'Component name: {component.name}')
    except Exception as e:
        print(f'Error: {e}')
        traceback.print_exc()

asyncio.run(test())