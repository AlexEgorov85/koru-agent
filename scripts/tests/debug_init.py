import asyncio
import traceback
from core.config.models import SystemConfig
from core.system_context.system_context import SystemContext
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
        
        print("Creating SystemContext...")
        system_context = SystemContext(config)
        print('SystemContext created successfully')
        print('Registry type:', type(system_context.registry))
        print('Registry has register_resource:', hasattr(system_context.registry, 'register_resource'))
        print('Registry has register_capability:', hasattr(system_context.registry, 'register_capability'))
        
        print("Calling initialize...")
        success = await system_context.initialize()
        print('Initialization success:', success)
    except Exception as e:
        print('Exception occurred:', str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())