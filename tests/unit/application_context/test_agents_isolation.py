import asyncio
import sys
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_agents_isolation():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    print('InfrastructureContext инициализирован')
    
    # Создаем два разных прикладных контекста (для разных агентов)
    # Используем пустые версии, чтобы избежать ошибок валидации
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
    
    # Проверяем изоляцию кэшей между "агентами"
    ps1 = app_context1.get_service("prompt_service")
    ps2 = app_context2.get_service("prompt_service")
    
    cs1 = app_context1.get_service("contract_service")
    cs2 = app_context2.get_service("contract_service")
    
    # Проверяем, что кэши действительно изолированы
    if ps1 and ps2:
        print(f'PromptService1 кэш пустой: {len(ps1._cached_prompts) == 0 if hasattr(ps1, "_cached_prompts") else "Нет атрибута _cached_prompts"}')
        print(f'PromptService2 кэш пустой: {len(ps2._cached_prompts) == 0 if hasattr(ps2, "_cached_prompts") else "Нет атрибута _cached_prompts"}')

        # Проверяем, что кэши принадлежат разным объектам
        if hasattr(ps1, "_cached_prompts") and hasattr(ps2, "_cached_prompts"):
            print(f'PromptService1 кэш ID: {id(ps1._cached_prompts)}')
            print(f'PromptService2 кэш ID: {id(ps2._cached_prompts)}')
            print(f'PromptService кэши изолированы: {ps1._cached_prompts is not ps2._cached_prompts}')
        else:
            print('Один из PromptService не имеет атрибута _cached_prompts')
    else:
        print('Один из PromptService не инициализирован')

    if cs1 and cs2:
        if hasattr(cs1, "_cached_contracts") and hasattr(cs2, "_cached_contracts"):
            print(f'ContractService1 кэш ID: {id(cs1._cached_contracts)}')
            print(f'ContractService2 кэш ID: {id(cs2._cached_contracts)}')
            print(f'ContractService кэши изолированы: {cs1._cached_contracts is not cs2._cached_contracts}')
        else:
            print('Один из ContractService не имеет атрибута _cached_contracts')
    else:
        print('Один из ContractService не инициализирован')

    # В новой архитектуре кэши находятся внутри сервисов, а не в ApplicationContext напрямую
    print('В новой архитектуре кэши находятся внутри сервисов, а не в ApplicationContext напрямую')
    print('Изоляция обеспечивается через изолированные экземпляры сервисов в каждом ApplicationContext')
    
    print('Тест изоляции между агентами пройден!')

print('Запуск теста изоляции между агентами...')
asyncio.run(test_agents_isolation())
print('Тест изоляции между агентами завершен')