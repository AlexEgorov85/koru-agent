import sys
import asyncio
import traceback
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

print('Начало теста ApplicationContext')

async def test():
    print('Создание минимальной конфигурации')
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
        print('Конфигурации созданы')
    except Exception as e:
        print(f'Ошибка при создании конфигураций: {e}')
        traceback.print_exc()
        return

    print('Создание InfrastructureContext')
    try:
        infra = InfrastructureContext(system_config)
        result = await infra.initialize()
        print(f'InfrastructureContext инициализирован: {result}')
    except Exception as e:
        print(f'Ошибка при инициализации InfrastructureContext: {e}')
        traceback.print_exc()
        return

    print('Создание ApplicationContext')
    try:
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config
        )
        result = await app_context.initialize()
        print(f'ApplicationContext инициализирован: {result}')
        
        # Проверяем, что сервисы созданы в ApplicationContext
        prompt_service = app_context.get_service("prompt_service")
        contract_service = app_context.get_service("contract_service")
        print(f'PromptService в ApplicationContext: {prompt_service is not None}')
        print(f'ContractService в ApplicationContext: {contract_service is not None}')
        
        # Проверяем, что они имеют изолированные кэши
        if prompt_service:
            print(f'Type of prompt_service: {type(prompt_service)}')
            print(f'PromptService cache: {hasattr(prompt_service, "_cached_prompts")}')
        
        if contract_service:
            print(f'Type of contract_service: {type(contract_service)}')
            print(f'ContractService cache: {hasattr(contract_service, "_cached_contracts")}')
            
    except Exception as e:
        print(f'Ошибка при инициализации ApplicationContext: {e}')
        traceback.print_exc()

print('Запуск асинхронного теста')
try:
    asyncio.run(test())
    print('Тест ApplicationContext завершен')
except Exception as e:
    print(f'Ошибка при запуске теста: {e}')
    traceback.print_exc()