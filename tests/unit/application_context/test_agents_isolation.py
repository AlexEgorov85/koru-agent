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
    print(f'PromptService1 кэш пустой: {len(ps1._cached_prompts) == 0}')
    print(f'PromptService2 кэш пустой: {len(ps2._cached_prompts) == 0}')
    
    # Проверяем, что кэши принадлежат разным объектам
    print(f'PromptService1 кэш ID: {id(ps1._cached_prompts)}')
    print(f'PromptService2 кэш ID: {id(ps2._cached_prompts)}')
    print(f'PromptService кэши изолированы: {ps1._cached_prompts is not ps2._cached_prompts}')
    
    print(f'ContractService1 кэш ID: {id(cs1._cached_contracts)}')
    print(f'ContractService2 кэш ID: {id(cs2._cached_contracts)}')
    print(f'ContractService кэши изолированы: {cs1._cached_contracts is not cs2._cached_contracts}')
    
    # Проверяем, что каждый контекст имеет свои изолированные кэши
    print(f'ApplicationContext1 кэш ID: {id(app_context1._prompt_cache)}')
    print(f'ApplicationContext2 кэш ID: {id(app_context2._prompt_cache)}')
    print(f'ApplicationContext кэши изолированы: {app_context1._prompt_cache is not app_context2._prompt_cache}')
    
    print(f'Input contract кэши изолированы: {app_context1._input_contract_cache is not app_context2._input_contract_cache}')
    print(f'Output contract кэши изолированы: {app_context1._output_contract_cache is not app_context2._output_contract_cache}')
    
    print('Тест изоляции между агентами пройден!')

print('Запуск теста изоляции между агентами...')
asyncio.run(test_agents_isolation())
print('Тест изоляции между агентами завершен')