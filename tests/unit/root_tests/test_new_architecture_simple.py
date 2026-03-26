#!/usr/bin/env python3
"""
Тестирование новой архитектуры ApplicationContext
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig


async def test_application_context_structure(fake_infra_context):
    """Тестирование структуры ApplicationContext"""
    print("\n=== Тестирование структуры ApplicationContext ===")

    app_config = AppConfig(
        config_id="structure_test",
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

    # Проверяем структуру
    assert hasattr(app_context, 'infrastructure_context')
    assert hasattr(app_context, 'config')
    assert hasattr(app_context, 'profile')
    assert hasattr(app_context, 'components')
    assert hasattr(app_context, 'data_repository')

    print("✅ Все атрибуты ApplicationContext присутствуют")
    print(f"  - infrastructure_context: {app_context.infrastructure_context is not None}")
    print(f"  - config: {app_context.config is not None}")
    print(f"  - profile: {app_context.profile}")
    print(f"  - components: {app_context.components is not None}")
    print(f"  - data_repository: {app_context.data_repository is not None}")

    print("\n✅ Тест структуры ApplicationContext пройден")
