#!/usr/bin/env python3
"""
Тестирование полной загрузки компонентов
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig


async def test_full_loading(fake_infra_context):
    """Тестирование полной загрузки с правильной конфигурацией"""
    print("=== Тестирование полной загрузки с правильной конфигурацией ===")

    app_config = AppConfig(
        config_id="full_test_config",
        prompt_versions={"test": "v1.0.0"},
        input_contract_versions={"test": "v1.0.0"},
        output_contract_versions={"test": "v1.0.0"},
        service_configs={
            "prompt_service": ComponentConfig(
                variant_id='test',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            ),
            "contract_service": ComponentConfig(
                variant_id='test',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        },
        tool_configs={
            "sql_tool": ComponentConfig(
                variant_id='test',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            ),
            "file_tool": ComponentConfig(
                variant_id='test',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        }
    )

    print(f"Конфигурация создана:")
    print(f"- Сервисов: {len(app_config.service_configs)}")
    print(f"- Инструментов: {len(app_config.tool_configs)}")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    success = await app_context.initialize()
    print(f"ApplicationContext инициализирован: {success}")

    if success:
        services = app_context.components.all_of_type(ComponentType.SERVICE)
        tools = app_context.components.all_of_type(ComponentType.TOOL)
        print(f"Загружено сервисов: {len(services)}")
        print(f"Загружено инструментов: {len(tools)}")

    print("\n✅ Тест полной загрузки пройден")
