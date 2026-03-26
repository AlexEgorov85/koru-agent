import sys
import asyncio
import traceback
from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext


async def test():
    try:
        config = SystemConfig(
            llm_providers={},
            db_providers={},
            data_dir='data'
        )
    except Exception as e:
        traceback.print_exc()
        return

    try:
        infra = InfrastructureContext(config)
        result = await infra.initialize()
    except Exception as e:
        traceback.print_exc()
        return

    # Проверяем, что хранилища существуют
    try:
        prompt_storage = infra.get_prompt_storage()
        contract_storage = infra.get_contract_storage()
    except Exception as e:
        traceback.print_exc()

    # Проверяем, что метод get_service больше не существует или возвращает None для сервисов
    try:
        service = infra.get_service('prompt_service')
    except AttributeError as e:
    except Exception as e:
        traceback.print_exc()

try:
    asyncio.run(test())
except Exception as e:
    traceback.print_exc()