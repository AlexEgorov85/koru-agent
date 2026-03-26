import asyncio
import sys
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_skills_isolation():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    
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
    if ps1 and ps2:
        if hasattr(ps1, "_cached_prompts") and hasattr(ps2, "_cached_prompts"):

            # Проверяем, что кэши принадлежат разным объектам
        else:
    else:

    # В новой архитектуре кэши находятся внутри сервисов, а не в ApplicationContext напрямую

asyncio.run(test_skills_isolation())
