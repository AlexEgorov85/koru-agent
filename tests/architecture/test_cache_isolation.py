#!/usr/bin/env python3
"""
Тест изоляции кэшей между агентами.
"""
import pytest
import asyncio
from pathlib import Path

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.fixture
async def infra():
    """Создание InfrastructureContext для тестов."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.fixture
async def app_context_pair(infra):
    """Создание пары изолированных ApplicationContext."""
    # Используем минимальную конфигурацию только с сервисами
    app_config = AppConfig(
        config_id="test_isolation",
        service_configs={
            'prompt_service': {
                'variant_id': 'prompt_service_default',
                'prompt_versions': {},
                'input_contract_versions': {},
                'output_contract_versions': {},
                'side_effects_enabled': True,
                'detailed_metrics': False,
                'parameters': {},
                'dependencies': []
            },
            'contract_service': {
                'variant_id': 'contract_service_default',
                'prompt_versions': {},
                'input_contract_versions': {},
                'output_contract_versions': {},
                'side_effects_enabled': True,
                'detailed_metrics': False,
                'parameters': {},
                'dependencies': []
            }
        }
    )
    
    ctx1 = ApplicationContext(infra, app_config, profile='test')
    ctx2 = ApplicationContext(infra, app_config, profile='test')
    
    success1 = await ctx1.initialize()
    success2 = await ctx2.initialize()
    
    if not success1 or not success2:
        pytest.fail(f"ApplicationContext не инициализировался: ctx1={success1}, ctx2={success2}")
    
    yield ctx1, ctx2


@pytest.mark.asyncio
async def test_infrastructure_shared_between_agents(infra):
    """Инфраструктура должна быть ОБЩЕЙ между агентами."""
    app_config = AppConfig.from_registry(profile='prod')
    ctx1 = ApplicationContext(infra, app_config, profile='prod')
    ctx2 = ApplicationContext(infra, app_config, profile='prod')

    await ctx1.initialize()
    await ctx2.initialize()

    # Инфраструктура должна быть одним объектом
    assert ctx1.infrastructure_context is ctx2.infrastructure_context
    # Проверяем, что resource_registry один и тот же (общий доступ к ресурсам)
    assert id(ctx1.infrastructure_context.resource_registry) == id(ctx2.infrastructure_context.resource_registry)
    print("[PASS] Инфраструктура общая между агентами")


@pytest.mark.asyncio
async def test_application_context_isolated(infra):
    """ApplicationContext должен быть ИЗОЛИРОВАННЫМ между агентами."""
    app_config = AppConfig.from_registry(profile='prod')
    ctx1 = ApplicationContext(infra, app_config, profile='prod')
    ctx2 = ApplicationContext(infra, app_config, profile='prod')

    await ctx1.initialize()
    await ctx2.initialize()

    # Контексты должны быть разными объектами
    assert ctx1 is not ctx2
    assert id(ctx1.components) != id(ctx2.components)
    print("✅ ApplicationContext изолирован между агентами")


@pytest.mark.asyncio
async def test_prompt_cache_isolated(app_context_pair):
    """Кэши промптов должны быть ИЗОЛИРОВАННЫМИ между агентами."""
    ctx1, ctx2 = app_context_pair

    # Получаем сервисы промптов через components registry
    from core.application.context.application_context import ComponentType
    prompt_service1 = ctx1.components.get(ComponentType.SERVICE, 'prompt_service')
    prompt_service2 = ctx2.components.get(ComponentType.SERVICE, 'prompt_service')

    # Проверяем, что сервисы существуют
    assert prompt_service1 is not None, "PromptService не создан в ctx1"
    assert prompt_service2 is not None, "PromptService не создан в ctx2"

    # Кэши должны быть разными объектами (изолированными)
    if hasattr(prompt_service1, '_cached_prompts') and hasattr(prompt_service2, '_cached_prompts'):
        assert id(prompt_service1._cached_prompts) != id(prompt_service2._cached_prompts)

    print("[PASS] Кэши промптов изолированы")


@pytest.mark.asyncio
async def test_contract_cache_isolated(app_context_pair):
    """Кэши контрактов должны быть ИЗОЛИРОВАННЫМИ между агентами."""
    ctx1, ctx2 = app_context_pair

    # Получаем сервисы контрактов
    contract_service1 = ctx1.get_service('contract_service')
    contract_service2 = ctx2.get_service('contract_service')

    # Проверяем, что сервисы существуют
    assert contract_service1 is not None, "ContractService не создан в ctx1"
    assert contract_service2 is not None, "ContractService не создан в ctx2"

    # Кэши должны быть разными объектами (изолированными)
    assert id(contract_service1._cached_contracts) != id(contract_service2._cached_contracts)

    print("[PASS] Кэши контрактов изолированы")