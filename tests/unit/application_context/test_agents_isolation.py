import asyncio
import sys
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_agents_isolation():
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    
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

        # Проверяем, что кэши принадлежат разным объектам
        if hasattr(ps1, "_cached_prompts") and hasattr(ps2, "_cached_prompts"):
        else:
    else:

    if cs1 and cs2:
        if hasattr(cs1, "_cached_contracts") and hasattr(cs2, "_cached_contracts"):
        else:
    else:

    # В новой архитектуре кэши находятся внутри сервисов, а не в ApplicationContext напрямую
    

asyncio.run(test_agents_isolation())
