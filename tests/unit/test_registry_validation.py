#!/usr/bin/env python3
"""
Тест для проверки валидации реестра промптов
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.registry.prompt_registry import PromptRegistry
from pathlib import Path
import os


def test_registry_validation():
    print("=== Тест валидации реестра промптов ===")
    
    try:
        # Создаём реестр промптов с абсолютным путем
        current_dir = os.path.dirname(os.path.abspath(__file__))
        registry_path = os.path.join(current_dir, "prompts", "registry.yaml")
        
        print(f"Путь к реестру: {registry_path}")
        
        # Проверяем существование файла
        if not os.path.exists(registry_path):
            print(f"- Файл реестра не найден: {registry_path}")
            return False
            
        print("+ Файл реестра найден")
        
        # Создаём реестр
        registry = PromptRegistry(registry_path=Path(registry_path))
        
        print(f"+ Реестр загружен, версия: {registry.registry_data.get('registry_version')}")
        print(f"+ Количество активных промптов: {len(registry.active_prompts)}")
        
        # Проверяем, что все промпты из реестра существуют как файлы
        all_files_exist = True
        for capability, entry in registry.active_prompts.items():
            file_path = os.path.join(current_dir, "prompts", entry.file_path)
            if os.path.exists(file_path):
                print(f"  + Файл для {capability}: {entry.file_path} - OK")
            else:
                print(f"  - Файл для {capability}: {entry.file_path} - НЕ НАЙДЕН")
                all_files_exist = False
                
        if not all_files_exist:
            print("- Не все файлы промптов существуют")
            return False
            
        # Проверяем конкретный промпт
        if "planning.create_plan" in registry.active_prompts:
            print("+ Промпт planning.create_plan есть в реестре")
            
            # Попробуем загрузить его
            prompt = registry.get_active_prompt("planning.create_plan")
            if prompt:
                print(f"+ Промпт planning.create_plan успешно загружен")
                print(f"  - capability: {prompt.metadata.capability}")
                print(f"  - version: {prompt.metadata.version}")
                print(f"  - content length: {len(prompt.content)}")
                return True
            else:
                print("- Не удалось загрузить промпт planning.create_plan")
                return False
        else:
            print("- Промпт planning.create_plan отсутствует в реестре")
            print("  Доступные промпты:", list(registry.active_prompts.keys()))
            return False
            
    except Exception as e:
        print(f"- Ошибка при работе с реестром: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_registry_validation()
    if success:
        print("\n+ Валидация реестра пройдена успешно!")
    else:
        print("\n- Валидация реестра не пройдена!")
        sys.exit(1)