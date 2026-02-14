import asyncio
import sys
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_skills_isolation():
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
    
    # Проверяем, что навыки используют изолированные кэши
    # Хотя мы не создаем конкретные навыки, мы можем проверить, что у каждого
    # прикладного контекста есть доступ к изолированным сервисам, которые
    # обеспечивают изолированные кэши для навыков
    
    ps1 = app_context1.get_service("prompt_service")
    ps2 = app_context2.get_service("prompt_service")
    
    # Проверяем, что кэши действительно изолированы
    print(f'PromptService1 кэш пустой: {len(ps1._cached_prompts) == 0}')
    print(f'PromptService2 кэш пустой: {len(ps2._cached_prompts) == 0}')
    
    # Проверяем, что кэши принадлежат разным объектам
    print(f'PromptService1 кэш ID: {id(ps1._cached_prompts)}')
    print(f'PromptService2 кэш ID: {id(ps2._cached_prompts)}')
    print(f'Кэши изолированы: {ps1._cached_prompts is not ps2._cached_prompts}')
    
    # Проверим, что у каждого контекста есть доступ к своим изолированным кэшам
    print(f'app_context1 имеет доступ к изолированному кэшу: {hasattr(app_context1, "_prompt_cache")}')
    print(f'app_context2 имеет доступ к изолированному кэшу: {hasattr(app_context2, "_prompt_cache")}')
    
    print(f'app_context1 кэш ID: {id(app_context1._prompt_cache)}')
    print(f'app_context2 кэш ID: {id(app_context2._prompt_cache)}')
    print(f'Кэши контекстов изолированы: {app_context1._prompt_cache is not app_context2._prompt_cache}')

print('Запуск теста изоляции навыков...')
asyncio.run(test_skills_isolation())
print('Тест изоляции навыков завершен')