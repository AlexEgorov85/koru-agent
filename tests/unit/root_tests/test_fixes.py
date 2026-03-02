#!/usr/bin/env python3
"""
Тестирование исправлений для регистрации компонентов
"""
import pytest
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.config_loader import ConfigLoader
from core.models.data.manifest import ComponentType


@pytest.fixture
async def app_context():
    """Создание ApplicationContext для тестов."""
    config_loader = ConfigLoader(profile="dev", config_dir="core/config/defaults")
    system_config = config_loader.load()

    infra_context = InfrastructureContext(config=system_config)
    await infra_context.initialize()

    app_config = AppConfig.from_discovery(profile="sandbox", data_dir="data")

    app_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="sandbox"
    )

    await app_context.initialize()

    yield app_context

    await infra_context.shutdown()


@pytest.mark.asyncio
async def test_component_registration(app_context):
    """Тестирование регистрации компонентов."""
    # Проверяем зарегистрированные компоненты
    skills = app_context.components.all_of_type(ComponentType.SKILL)
    tools = app_context.components.all_of_type(ComponentType.TOOL)
    services = app_context.components.all_of_type(ComponentType.SERVICE)

    assert len(skills) > 0, "Should have registered skills"
    assert len(tools) > 0, "Should have registered tools"
    assert len(services) > 0, "Should have registered services"


@pytest.mark.asyncio
async def test_specific_skills(app_context):
    """Тестирование конкретных навыков."""
    planning_skill = app_context.get_skill("planning")
    book_library_skill = app_context.get_skill("book_library")

    assert planning_skill is not None, "Planning skill should be registered"
    assert book_library_skill is not None, "Book library skill should be registered"


@pytest.mark.asyncio
async def test_specific_tools(app_context):
    """Тестирование конкретных инструментов."""
    sql_tool = app_context.get_tool("sql_tool")
    file_tool = app_context.get_tool("file_tool")

    assert sql_tool is not None, "SQL tool should be registered"
    assert file_tool is not None, "File tool should be registered"
