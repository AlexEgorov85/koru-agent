#!/usr/bin/env python3
"""
Тестирование загрузки конфигураций инструментов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig


async def test_config_loading(fake_infra_context):
    """Тестируем загрузку конфигураций"""

    # Создаем конфигурацию с инструментами
    app_config = AppConfig(
        config_id="config_test",
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
            )
        },
        tool_configs={
            "sql_tool": ComponentConfig(
                variant_id='test_sql_tool',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            ),
            "file_tool": ComponentConfig(
                variant_id='test_file_tool',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        }
    )


    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    # Проверим, что конфигурации компонентов извлекаются правильно
    component_configs = app_context._resolve_component_configs()
    for comp_type, configs in component_configs.items():

