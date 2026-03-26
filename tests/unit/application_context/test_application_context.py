import sys
import asyncio
import traceback
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext


async def test():
    try:
        system_config = SystemConfig(
            llm_providers={},
            db_providers={},
            data_dir='data'
        )
        app_config = AppConfig(
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False
        )
    except Exception as e:
        traceback.print_exc()
        return

    try:
        infra = InfrastructureContext(system_config)
        result = await infra.initialize()
    except Exception as e:
        traceback.print_exc()
        return

    try:
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config
        )
        result = await app_context.initialize()
        
        # Проверяем, что сервисы созданы в ApplicationContext
        prompt_service = app_context.get_service("prompt_service")
        contract_service = app_context.get_service("contract_service")
        
        # Проверяем, что они имеют изолированные кэши
        if prompt_service:
        
        if contract_service:
            
    except Exception as e:
        traceback.print_exc()

try:
    asyncio.run(test())
except Exception as e:
    traceback.print_exc()