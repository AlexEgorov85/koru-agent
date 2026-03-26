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
    
    # Создаем конфигурацию приложения из реестра
    app_config = AppConfig.from_discovery(profile="sandbox", data_dir="data")
    
    
    # Проверим детали конфигурации навыков
    for skill_name, skill_config in app_config.skill_configs.items():
    
    # Проверим детали конфигурации инструментов
    for tool_name, tool_config in app_config.tool_configs.items():
    


if __name__ == "__main__":
    asyncio.run(test_config_loading())