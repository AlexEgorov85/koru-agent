import asyncio
import sys
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_application_context_isolation():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    print('InfrastructureContext инициализирован')
    
    # Создаем два разных прикладных контекста
    app_config1 = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    
    app_config2 = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    
    app_context1 = ApplicationContext(
        infrastructure_context=infra,
        config=app_config1
    )
    await app_context1.initialize()
    
    app_context2 = ApplicationContext(
        infrastructure_context=infra,
        config=app_config2
    )
    await app_context2.initialize()
    
    # Проверяем, что сервисы изолированы
    ps1 = app_context1.get_service("prompt_service")
    ps2 = app_context2.get_service("prompt_service")
    
    cs1 = app_context1.get_service("contract_service")
    cs2 = app_context2.get_service("contract_service")
    
    print(f'PromptService в контексте 1: {ps1 is not None}')
    print(f'PromptService в контексте 2: {ps2 is not None}')
    print(f'ContractService в контексте 1: {cs1 is not None}')
    print(f'ContractService в контексте 2: {cs2 is not None}')
    
    # Проверяем изоляцию кэшей
    print(f'PromptService1 ID: {id(ps1)}')
    print(f'PromptService2 ID: {id(ps2)}')
    print(f'ContractService1 ID: {id(cs1)}')
    print(f'ContractService2 ID: {id(cs2)}')
    
    # Проверяем, что это разные объекты (изоляция)
    print(f'PromptService изолированы: {ps1 is not ps2}')
    print(f'ContractService изолированы: {cs1 is not cs2}')
    
    # Проверяем, что кэши изолированы
    print(f'PromptService1 кэш: {hasattr(ps1, "_cached_prompts")}')
    print(f'PromptService2 кэш: {hasattr(ps2, "_cached_prompts")}')
    print(f'ContractService1 кэш: {hasattr(cs1, "_cached_contracts")}')
    print(f'ContractService2 кэш: {hasattr(cs2, "_cached_contracts")}')

print('Запуск теста изоляции...')
asyncio.run(test_application_context_isolation())
print('Тест изоляции завершен')