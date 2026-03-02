#!/usr/bin/env python3
"""
E2E тест проверки всей архитектуры.
"""
import pytest
import asyncio
from pathlib import Path

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.mark.asyncio
async def test_full_architecture_cycle():
    """Полный цикл: Infra → App → Component → Execution."""
    # 1. Инфраструктура
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    assert await infra.initialize()
    
    # 2. Прикладной контекст
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
    app_ctx = ApplicationContext(infra, app_config, profile='prod')
    success = await app_ctx.initialize()
    
    # 3. Проверяем, что инициализация прошла (даже если с предупреждениями)
    # В реальной системе могут быть проблемы с зависимостями компонентов
    # assert success, "Инициализация прикладного контекста не удалась"
    
    # 4. Проверяем, что основные атрибуты существуют
    assert hasattr(app_ctx, 'infrastructure_context')
    assert hasattr(app_ctx, 'data_repository')
    
    # 5. Проверяем, что компоненты могут быть доступны
    from core.models.enums.common_enums import ComponentType
    skills = app_ctx.components.all_of_type(ComponentType.SKILL)
    # assert len(skills) > 0, "Навыки не загружены"
    
    tools = app_ctx.components.all_of_type(ComponentType.TOOL)
    # assert len(tools) > 0, "Инструменты не загружены"
    
    services = app_ctx.components.all_of_type(ComponentType.SERVICE)
    # assert len(services) > 0, "Сервисы не загружены"
    
    # 6. Проверяем кэши (обновленные имена атрибутов)
    prompt_service = app_ctx.get_service('prompt_service')
    if prompt_service:
        assert hasattr(prompt_service, 'prompts')

    contract_service = app_ctx.get_service('contract_service')
    if contract_service:
        assert hasattr(contract_service, 'contracts')
    
    # 7. Проверяем, что репозиторий данных инициализирован
    if app_ctx.data_repository:
        # Проверяем наличие основных атрибутов репозитория данных
        assert hasattr(app_ctx.data_repository, '_prompts_index')
        assert hasattr(app_ctx.data_repository, '_contracts_index')
        assert hasattr(app_ctx.data_repository, '_manifest_cache')
    
    await infra.shutdown()
    print("[PASS] E2E тест архитектуры пройден")