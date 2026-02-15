import asyncio
import traceback
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
import tempfile
import os

async def test():
    try:
        temp_dir = os.path.join(tempfile.gettempdir(), 'test')
        os.makedirs(temp_dir, exist_ok=True)
        
        config = SystemConfig()
        config.log_dir = temp_dir
        config.profile = 'dev'
        config.log_level = 'DEBUG'
        config.llm_providers = {}
        config.db_providers = {}
        
        print("Creating InfrastructureContext...")
        infrastructure_context = InfrastructureContext(config)
        print('InfrastructureContext created successfully')

        print("Calling initialize...")
        success = await infrastructure_context.initialize()
        print('Infrastructure initialization success:', success)

        if success:
            print("Creating ApplicationContext...")
            application_context = await ApplicationContext.create_from_registry(
                infrastructure_context=infrastructure_context,
                profile="prod"
            )
            print('ApplicationContext created successfully')
            print('Components registry type:', type(application_context.components))
            print('Components registry has register:', hasattr(application_context.components, 'register'))
            print('Components registry has get:', hasattr(application_context.components, 'get'))
    except Exception as e:
        print('Exception occurred:', str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())