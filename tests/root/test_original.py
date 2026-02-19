#!/usr/bin/env python3
"""
Тестирование оригинального кода инициализации ApplicationContext.
"""
import asyncio
import pytest
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.models import SystemConfig


@pytest.fixture
async def infra_context():
    """Создание InfrastructureContext для тестов."""
    config = SystemConfig()
    config.profile = "prod"
    config.data_dir = "data"

    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.mark.asyncio
async def test_original_code_initialization(infra_context):
    """Тест оригинального кода инициализации ApplicationContext."""
    ctx1 = ApplicationContext(
        infrastructure_context=infra_context,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )

    assert ctx1 is not None, "ApplicationContext should be created"

    success = await ctx1.initialize()
    assert success, "ApplicationContext should initialize successfully"