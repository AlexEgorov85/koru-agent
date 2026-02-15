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
    print("=== Тестирование исправления конфигурации sql_tool ===")
    
    try:
        # Импортируем необходимые модули
        from core.config.app_config import AppConfig
        
        print("+ Импорт модулей выполнен успешно")
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_registry(profile="prod")
        print(f"+ AppConfig загружен из реестра, профиль: {app_config.profile}")
        print(f"  - prompt_versions (глобальные): {len(app_config.prompt_versions)} записей")
        print(f"  - tool_configs: {len(app_config.tool_configs)} инструментов")
        
        # Проверяем конфигурацию sql_tool
        if 'sql_tool' in app_config.tool_configs:
            sql_tool_config = app_config.tool_configs['sql_tool']
            print(f"+ Конфигурация sql_tool найдена:")
            print(f"  - prompt_versions: {sql_tool_config.prompt_versions}")
            print(f"  - input_contract_versions: {sql_tool_config.input_contract_versions}")
            print(f"  - output_contract_versions: {sql_tool_config.output_contract_versions}")
            
            # Проверяем, что конфигурация инструмента НЕ содержит глобальные версии навыков
            global_prompt_keys = set(app_config.prompt_versions.keys())
            tool_prompt_keys = set(sql_tool_config.prompt_versions.keys())
            
            if tool_prompt_keys.intersection(global_prompt_keys):
                print("- ОШИБКА: Конфигурация sql_tool содержит глобальные версии навыков!")
                print(f"  Пересечение: {tool_prompt_keys.intersection(global_prompt_keys)}")
                return False
            else:
                print("+ УСПЕХ: Конфигурация sql_tool НЕ содержит глобальные версии навыков")
                
            # Проверяем, что конфигурация инструмента пуста (что правильно для инструментов без промптов)
            if not sql_tool_config.prompt_versions and not sql_tool_config.input_contract_versions and not sql_tool_config.output_contract_versions:
                print("+ УСПЕХ: Конфигурация sql_tool пуста (нормально для инструментов без промптов)")
            else:
                print("! ВНИМАНИЕ: Конфигурация sql_tool содержит какие-то версии")
                
        else:
            print("- ОШИБКА: Конфигурация sql_tool НЕ найдена!")
            return False
        
        print("\n=== ОСНОВНОЙ ТЕСТ ПРОЙДЕН: sql_tool правильно настроен ===")
        print("Ключевой момент: инструменты больше не получают версии навыков по умолчанию!")
        return True
        
    except Exception as e:
        print(f"- ОШИБКА при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sql_tool_config_fix()
    if success:
        print("\n+ Все основные тесты пройдены успешно!")
        sys.exit(0)
    else:
        print("\n- Основные тесты не пройдены!")
        sys.exit(1)