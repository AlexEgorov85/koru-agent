import sys
import asyncio
import traceback
from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext

print('Начало теста')

async def test():
    print('Создание минимальной конфигурации')
    try:
        config = SystemConfig(
            llm_providers={},
            db_providers={},
            data_dir='data'
        )
        print('Конфигурация создана')
    except Exception as e:
        print(f'Ошибка при создании конфигурации: {e}')
        traceback.print_exc()
        return

    print('Создание InfrastructureContext')
    try:
        infra = InfrastructureContext(config)
        print('Инициализация InfrastructureContext')
        result = await infra.initialize()
        print(f'InfrastructureContext инициализирован: {result}')
    except Exception as e:
        print(f'Ошибка при инициализации InfrastructureContext: {e}')
        traceback.print_exc()
        return

    # Проверяем, что хранилища существуют
    try:
        prompt_storage = infra.get_prompt_storage()
        contract_storage = infra.get_contract_storage()
        print(f'PromptStorage доступен: {prompt_storage is not None}')
        print(f'ContractStorage доступен: {contract_storage is not None}')
    except Exception as e:
        print(f'Ошибка при доступе к хранилищам: {e}')
        traceback.print_exc()

    # Проверяем, что метод get_service больше не существует или возвращает None для сервисов
    try:
        service = infra.get_service('prompt_service')
        print(f'get_service для prompt_service: {service}')
    except AttributeError as e:
        print(f'get_service не существует (ожидаемое поведение): {e}')
    except Exception as e:
        print(f'get_service вызвал другую ошибку: {e}')
        traceback.print_exc()

print('Запуск асинхронного теста')
try:
    asyncio.run(test())
    print('Тест завершен')
except Exception as e:
    print(f'Ошибка при запуске теста: {e}')
    traceback.print_exc()