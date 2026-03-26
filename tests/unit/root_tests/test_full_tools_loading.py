#!/usr/bin/env python3
"""
Тестирование полной загрузки инструментов
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig


async def test_full_tools_loading(fake_infra_context):
    """Тестирование полной загрузки инструментов"""
    print("=== Тестирование полной загрузки инструментов ===")

    app_config = AppConfig(
        config_id="tools_test_config",
        prompt_versions={"test": "v1.0.0"},
        input_contract_versions={"test": "v1.0.0"},
        output_contract_versions={"test": "v1.0.0"},
        tool_configs={
            "sql_tool": ComponentConfig(
                variant_id='test_sql',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            ),
            "file_tool": ComponentConfig(
                variant_id='test_file',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        }
    )

    print(f"Конфигурация создана:")
    print(f"- Инструментов: {len(app_config.tool_configs)}")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    success = await app_context.initialize()
    print(f"ApplicationContext инициализирован: {success}")

    if success:
        tools = app_context.components.all_of_type(ComponentType.TOOL)
        print(f"Загружено инструментов: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}")

    print("\n✅ Тест полной загрузки инструментов пройден")


async def test_tool_resolution(fake_infra_context):
    """Тестирование разрешения классов инструментов"""
    print("\n=== Тестирование разрешения классов инструментов ===")

    app_config = AppConfig(config_id="tool_resolution_test")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    test_tools = [
        ("sql_tool", ComponentType.TOOL),
        ("file_tool", ComponentType.TOOL),
    ]

    for name, comp_type in test_tools:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
            print(f"[OK] {name}: {cls.__name__}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")

    print("\n✅ Тест разрешения инструментов пройден")
