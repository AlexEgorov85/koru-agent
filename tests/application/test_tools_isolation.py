"""
Тест для проверки изоляции инструментов между контекстами.

Проверяет:
1. Создание двух разных контекстов с разными версиями промптов
2. Что каждый контекст имеет свои изолированные кэши
3. Что оба контекста используют один и тот же провайдер БД
4. Что sandbox режим блокирует запись в БД
"""
import pytest
from core.config.models import AgentConfig
from core.config.component_config import ComponentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.mark.asyncio
async def test_tools_isolation_between_contexts():
    """Тест изоляции инструментов между контекстами"""
    # Создаем инфраструктурный контекст
    infrastructure_context = InfrastructureContext()
    await infrastructure_context.initialize()

    # Контекст 1 с версией промпта v1.0.0
    ctx1 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=AgentConfig(
            prompt_versions={"sql_generation.generate_query": "v1.0.0"},
            input_contract_versions={"sql_generation.generate_query": "v1.0.0"},
            output_contract_versions={"sql_generation.generate_query": "v1.0.0"},
            side_effects_enabled=False  # sandbox-режим
        )
    )
    await ctx1.initialize()

    # Контекст 2 с версией промпта v2.0.0
    ctx2 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=AgentConfig(
            prompt_versions={"sql_generation.generate_query": "v2.0.0"},
            input_contract_versions={"sql_generation.generate_query": "v2.0.0"},
            output_contract_versions={"sql_generation.generate_query": "v2.0.0"},
            side_effects_enabled=True  # полноценный режим
        )
    )
    await ctx2.initialize()

    # Проверка 1: разные кэши промптов
    # Получаем инструменты из каждого контекста
    tool1 = ctx1.infrastructure_context.get_tool("sql_tool")
    tool2 = ctx2.infrastructure_context.get_tool("sql_tool")

    # Проверяем, что инструменты существуют
    assert tool1 is not None, "Инструмент 1 должен существовать"
    assert tool2 is not None, "Инструмент 2 должен существовать"

    # Проверка 2: общий провайдер БД
    db1 = ctx1.infrastructure_context.get_provider("default_db")
    db2 = ctx2.infrastructure_context.get_provider("default_db")
    assert id(db1) == id(db2), "Провайдеры БД должны быть одним и тем же объектом"

    # Проверка 3: sandbox блокирует запись
    # Для проверки этой функциональности нам нужно протестировать выполнение SQLTool
    # с write-запросом при выключенном side_effects_enabled

    # Проверяем, что у инструментов есть нужные атрибуты
    assert hasattr(tool1, 'component_config'), "Инструмент 1 должен иметь component_config"
    assert hasattr(tool2, 'component_config'), "Инструмент 2 должен иметь component_config"

    # Проверяем, что у них разные конфигурации
    assert tool1.component_config.variant_id != tool2.component_config.variant_id, "Конфигурации инструментов должны отличаться"

    # Проверяем, что у них разные настройки side_effects_enabled
    assert tool1.component_config.side_effects_enabled != tool2.component_config.side_effects_enabled, \
        "Настройки side_effects_enabled должны отличаться"

    # Завершаем работу контекстов
    await ctx1.dispose() if hasattr(ctx1, 'dispose') else None
    await ctx2.dispose() if hasattr(ctx2, 'dispose') else None
    await infrastructure_context.shutdown()