import tempfile
import os
from pathlib import Path
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ApplicationContext

async def test_fix():
    # Используем директорию data/
    config = SystemConfig(data_dir='data')
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    # Загружаем конфигурацию из реестра
    app_config = AppConfig.from_registry(profile='prod')
    
    app_context = ApplicationContext(infra, app_config, profile='prod')
    
    success = await app_context.initialize()
    
    print(f'Initialization success: {success}')
    
    await infra.shutdown()

import asyncio
asyncio.run(test_fix())