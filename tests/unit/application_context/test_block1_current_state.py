import asyncio
import sys
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext

async def test_current_state():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    print('InfrastructureContext инициализирован')
    print(f'prompt_storage: {infra.get_prompt_storage() is not None}')
    print(f'contract_storage: {infra.get_contract_storage() is not None}')
    # Проверим, что метод get_service больше не существует (это правильно)
    try:
        result = infra.get_service("prompt_service")
        print(f'get_service для prompt_service: Существует (неправильно)')
    except AttributeError:
        print(f'get_service для prompt_service: Не существует (правильно)')
    
    try:
        result = infra.get_service("contract_service")
        print(f'get_service для contract_service: Существует (неправильно)')
    except AttributeError:
        print(f'get_service для contract_service: Не существует (правильно)')
    
    # Проверим, что провайдеры работают
    print(f'get_provider для любого провайдера: {infra.get_provider("any") is None}')  # Должно быть True (None)

print('Запуск теста...')
asyncio.run(test_current_state())
print('Тест завершен')