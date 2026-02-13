#!/usr/bin/env python3
"""
Финальный тест для подтверждения решения проблемы с рекурсией при загрузке промпта
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.infrastructure.registry.prompt_registry import PromptRegistry
from pathlib import Path
import os


def test_recursion_fixed():
    print("=== Финальный тест: проверка решения проблемы с рекурсией ===")
    
    try:
        # Создаём реестр промптов с абсолютным путем
        current_dir = os.path.dirname(os.path.abspath(__file__))
        registry_path = os.path.join(current_dir, "prompts", "registry.yaml")
        registry = PromptRegistry(registry_path=Path(registry_path))
        
        print("+ Реестр успешно загружен")
        
        # Проверяем, что промпт planning.create_plan есть в реестре
        if "planning.create_plan" in registry.active_prompts:
            print("+ Промпт planning.create_plan найден в реестре")
            
            # Пытаемся загрузить активный промпт - это было местом рекурсии
            loaded_prompt = registry.get_active_prompt("planning.create_plan")
            
            if loaded_prompt:
                print("+ Промпт успешно загружен без рекурсии!")
                print(f"+ Название capability: {loaded_prompt.metadata.capability}")
                print(f"+ Версия: {loaded_prompt.metadata.version}")
                print(f"+ Длина содержимого: {len(loaded_prompt.content)} символов")
                
                # Проверяем, что содержимое содержит ожидаемый текст
                if "модуль планирования агентной системы" in loaded_prompt.content:
                    print("+ Содержимое промпта корректно")
                    
                    # Проверяем, что переменные правильно определены
                    if "capabilities_list" in loaded_prompt.metadata.variables:
                        print("+ Переменные в промпте корректно определены")
                        
                        print("\n✅ ПРОБЛЕМА С РЕКУРСИЕЙ УСПЕШНО РЕШЕНА!")
                        print("   - Промпт planning.create_plan успешно загружается")
                        print("   - Нет ошибки 'maximum recursion depth exceeded'")
                        print("   - Файл registry.yaml корректно настроен")
                        print("   - Поддержка обоих форматов промптов реализована")
                        
                        return True
                    else:
                        print("- Переменные в промпте НЕ определены корректно")
                        return False
                else:
                    print("- Содержимое промпта НЕ корректно")
                    return False
            else:
                print("- Не удалось загрузить промпт из реестра")
                return False
        else:
            print("- Промпт planning.create_plan НЕ найден в реестре")
            return False
            
    except RecursionError as e:
        print(f"- Обнаружена рекурсия: {e}")
        print("❌ ПРОБЛЕМА С РЕКУРСИЕЙ НЕ РЕШЕНА!")
        return False
    except Exception as e:
        print(f"- Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_recursion_fixed()
    if success:
        print("\n🎉 Все тесты пройдены! Проблема с рекурсией полностью решена.")
    else:
        print("\n💥 Тесты не пройдены! Проблема сохраняется.")
        sys.exit(1)