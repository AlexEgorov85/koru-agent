#!/usr/bin/env python3
"""
Простой тест для проверки работы реестра промптов
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.registry.prompt_registry import PromptRegistry
from pathlib import Path


def test_registry_loading():
    print("=== Тест загрузки реестра промптов ===")
    
    try:
        # Создаём реестр промптов с абсолютным путем
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        registry_path = os.path.join(current_dir, "prompts", "registry.yaml")
        registry = PromptRegistry(registry_path=Path(registry_path))
        
        # Проверяем, что реестр загрузился
        print(f"+ Реестр загружен, версия: {registry.registry_data.get('registry_version')}")
        print(f"+ Автор: {registry.registry_data.get('author')}")
        
        # Проверяем количество активных промптов
        print(f"+ Количество активных промптов в реестре: {len(registry.active_prompts)}")
        
        # Проверяем наличие нашего промпта
        if "planning.create_plan" in registry.active_prompts:
            prompt_entry = registry.active_prompts["planning.create_plan"]
            print(f"+ Промпт planning.create_plan найден в реестре:")
            print(f"  - Версия: {prompt_entry.version}")
            print(f"  - Статус: {prompt_entry.status}")
            print(f"  - Файл: {prompt_entry.file_path}")
            
            # Попробуем загрузить сам промпт
            loaded_prompt = registry.get_active_prompt("planning.create_plan")
            if loaded_prompt:
                print(f"+ Промпт успешно загружен из файла")
                print(f"+ Название capability: {loaded_prompt.metadata.capability}")
                print(f"+ Версия: {loaded_prompt.metadata.version}")
                print(f"+ Длина содержимого: {len(loaded_prompt.content)} символов")
                
                # Показываем начало содержимого
                print("--- Начало содержимого промпта ---")
                print(loaded_prompt.content[:200] + "..." if len(loaded_prompt.content) > 200 else loaded_prompt.content)
                print("--- Конец начала содержимого ---")
                
                return True
            else:
                print("- Не удалось загрузить промпт из файла")
                return False
        else:
            print("- Промпт planning.create_plan НЕ найден в реестре")
            print("Доступные промпты:", list(registry.active_prompts.keys()))
            return False
            
    except Exception as e:
        print(f"- Ошибка при работе с реестром: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_registry_loading()
    if success:
        print("\n+ Тест реестра промптов пройден успешно!")
    else:
        print("\n- Тест реестра промптов завершился с ошибками!")
        sys.exit(1)