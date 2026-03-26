#!/usr/bin/env python3
"""
Тестирование с реальной конфигурацией из реестра
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig


async def test_real_registry_config(fake_infra_context):
    """Тестирование с реальной конфигурацией из реестра"""
    print("=== Тестирование с реальной конфигурацией из реестра ===")

    # Загружаем конфигурацию из реестра
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")

    print(f"Конфигурация загружена: {app_config.config_id}")
    print(f"Количество версий промптов: {len(app_config.prompt_versions)}")
    print(f"Количество версий входных контрактов: {len(app_config.input_contract_versions)}")
    print(f"Количество версий выходных контрактов: {len(app_config.output_contract_versions)}")
    print(f"Количество конфигураций сервисов: {len(app_config.service_configs)}")
    print(f"Сервисы в конфигурации: {list(app_config.service_configs.keys())}")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    success = await app_context.initialize()
    print(f"ApplicationContext инициализирован: {success}")

    if success:
        services = app_context.components.all_of_type(ComponentType.SERVICE)
        print(f"Загружено сервисов: {len(services)}")

    print("\n✅ Тест с реальной конфигурацией пройден")
