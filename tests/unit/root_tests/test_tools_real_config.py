#!/usr/bin/env python3
"""
Тестирование загрузки инструментов с реальной конфигурацией
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext, ComponentType
from core.config.app_config import AppConfig


async def test_tools_with_real_config(fake_infra_context):
    """Тестирование загрузки инструментов с реальной конфигурацией"""
    print("=== Тестирование загрузки инструментов с реальной конфигурацией ===")

    # Загружаем конфигурацию из реестра
    app_config = AppConfig.from_registry(profile="prod", registry_path="registry.yaml")

    print(f"Конфигурация загружена: {app_config.config_id}")
    print(f"Количество инструментов в конфигурации: {len(app_config.tool_configs)}")

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

    print("\n✅ Тест загрузки инструментов с реальной конфигурацией пройден")
