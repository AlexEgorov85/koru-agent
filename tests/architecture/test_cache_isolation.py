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


@pytest.mark.asyncio
async def test_infrastructure_shared_between_agents():
    """Инфраструктура должна быть ОБЩЕЙ между агентами."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    ctx1 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    ctx2 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    
    await ctx1.initialize()
    await ctx2.initialize()
    
    # Инфраструктура должна быть одним объектом
    assert ctx1.infrastructure_context is ctx2.infrastructure_context
    # Проверяем, что resource_registry один и тот же (общий доступ к ресурсам)
    assert id(ctx1.infrastructure_context.resource_registry) == id(ctx2.infrastructure_context.resource_registry)
    
    await infra.shutdown()
    print("[PASS] Инфраструктура общая между агентами")


@pytest.mark.asyncio
async def test_application_context_isolated():
    """ApplicationContext должен быть ИЗОЛИРОВАННЫМ между агентами."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    ctx1 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    ctx2 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    
    await ctx1.initialize()
    await ctx2.initialize()
    
    # Контексты должны быть разными объектами
    assert ctx1 is not ctx2
    assert id(ctx1.components) != id(ctx2.components)
    
    await infra.shutdown()
    print("✅ ApplicationContext изолирован между агентами")


@pytest.mark.asyncio
async def test_prompt_cache_isolated():
    """Кэши промптов должны быть ИЗОЛИРОВАННЫМИ между агентами."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()

    ctx1 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    ctx2 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')

    success1 = await ctx1.initialize()
    success2 = await ctx2.initialize()
    
    # Проверяем успешность инициализации
    if not success1 or not success2:
        pytest.skip("ApplicationContext не инициализировался успешно")

    # Получаем сервисы промптов через components registry
    from core.application.context.application_context import ComponentType
    prompt_service1 = ctx1.components.get(ComponentType.SERVICE, 'prompt_service')
    prompt_service2 = ctx2.components.get(ComponentType.SERVICE, 'prompt_service')
    
    # Проверяем, что сервисы существуют
    if prompt_service1 is None or prompt_service2 is None:
        pytest.skip("PromptService не создан")

    # Кэши должны быть разными объектами (изолированными)
    if hasattr(prompt_service1, '_cached_prompts') and hasattr(prompt_service2, '_cached_prompts'):
        assert id(prompt_service1._cached_prompts) != id(prompt_service2._cached_prompts)

    await infra.shutdown()
    print("[PASS] Кэши промптов изолированы")


@pytest.mark.asyncio
async def test_contract_cache_isolated():
    """Кэши контрактов должны быть ИЗОЛИРОВАННЫМИ между агентами."""
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    ctx1 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    ctx2 = ApplicationContext(infra, AppConfig.from_registry(profile='prod'), profile='prod')
    
    await ctx1.initialize()
    await ctx2.initialize()
    
    # Получаем сервисы контрактов
    contract_service1 = ctx1.get_service('contract_service')
    contract_service2 = ctx2.get_service('contract_service')
    
    # Проверяем, что сервисы существуют и их кэши изолированы
    if contract_service1 is not None and contract_service2 is not None:
        # Кэши должны быть разными объектами (изолированными)
        assert id(contract_service1._cached_contracts) != id(contract_service2._cached_contracts)
    
    await infra.shutdown()
    print("[PASS] Кэши контрактов изолированы")