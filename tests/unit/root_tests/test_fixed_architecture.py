#!/usr/bin/env python3
"""
Тестирование фиксированной архитектуры
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig


async def test_with_mock_infrastructure(fake_infra_context):
    """Тест с фиктивной инфраструктурой"""

    app_config = AppConfig(
        config_id="test_config",
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
        }
    )

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    success = await app_context.initialize()


async def test_resolve_component_class(fake_infra_context):
    """Тестирование _resolve_component_class"""

    app_config = AppConfig(config_id="test")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    # Тестируем разрешение компонентов
    test_components = [
        ("prompt_service", ComponentType.SERVICE),
        ("contract_service", ComponentType.SERVICE),
    ]

    for name, comp_type in test_components:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
        except Exception as e:

