#!/usr/bin/env python3
"""
Диагностический тест для проверки конфигурации компонентов
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.config.app_config import AppConfig


async def test_config_loading():
    """Тестирование загрузки конфигурации"""
    print("=== Тестирование загрузки конфигурации ===")
    
    # Создаем конфигурацию приложения из реестра
    app_config = AppConfig.from_discovery(profile="sandbox", data_dir="data")
    
    print(f"Конфигурация приложения загружена:")
    print(f"  - Навыки: {list(app_config.skill_configs.keys())}")
    print(f"  - Инструменты: {list(app_config.tool_configs.keys())}")
    print(f"  - Сервисы: {list(app_config.service_configs.keys())}")
    
    # Проверим детали конфигурации навыков
    for skill_name, skill_config in app_config.skill_configs.items():
        print(f"  - Навык '{skill_name}': {type(skill_config)} - {skill_config}")
    
    # Проверим детали конфигурации инструментов
    for tool_name, tool_config in app_config.tool_configs.items():
        print(f"  - Инструмент '{tool_name}': {type(tool_config)} - {tool_config}")
    
    print("=== Тестирование загрузки конфигурации завершено ===")


if __name__ == "__main__":
    asyncio.run(test_config_loading())