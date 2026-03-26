#!/usr/bin/env python3
"""
Простой тест для проверки исправления конфигурации sql_tool
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_sql_tool_config_fix():
    """Тестируем, что конфигурация sql_tool не содержит версии навыков"""
    
    try:
        # Импортируем необходимые модули
        from core.config.app_config import AppConfig
        
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        
        # Проверяем конфигурацию sql_tool
        if 'sql_tool' in app_config.tool_configs:
            sql_tool_config = app_config.tool_configs['sql_tool']
            
            # Проверяем, что конфигурация инструмента НЕ содержит глобальные версии навыков
            global_prompt_keys = set(app_config.prompt_versions.keys())
            tool_prompt_keys = set(sql_tool_config.prompt_versions.keys())
            
            if tool_prompt_keys.intersection(global_prompt_keys):
                assert False, "Конфигурация sql_tool содержит глобальные версии навыков"
            else:

            # Проверяем, что конфигурация инструмента пуста (что правильно для инструментов без промптов)
            if not sql_tool_config.prompt_versions and not sql_tool_config.input_contract_versions and not sql_tool_config.output_contract_versions:
            else:

        else:
            assert False, "Конфигурация sql_tool не найдена"

        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise  # Перебрасываем исключение для pytest