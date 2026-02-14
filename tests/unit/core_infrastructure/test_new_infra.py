import asyncio
import sys
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext

async def test():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    print(f'Initialized: {infra._initialized}')
    print(f'Resource registry: {infra.resource_registry}')
    print(f'Resource registry type: {type(infra.resource_registry)}')
    print(f'Get provider for nonexistent: {infra.get_provider("nonexistent")}')

print('Starting test...')
asyncio.run(test())
print('Test completed')