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

    # Загружаем конфигурацию из реестра
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")


    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    success = await app_context.initialize()

    if success:
        services = app_context.components.all_of_type(ComponentType.SERVICE)

