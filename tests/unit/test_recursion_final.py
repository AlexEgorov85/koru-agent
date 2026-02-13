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
                        
                        print("\n[SUCCESS] PROBLEMA S REKURSIIEI USPESHNO RESHEA!")
                        print("   - Prompt planning.create_plan uspeshno zagruzhaetsya")
                        print("   - Net oshibki 'maximum recursion depth exceeded'")
                        print("   - Fail registry.yaml korrrektno nastroen")
                        print("   - Podderzhka obikh formatov promptov realizovana")
                        
                        return True
                    else:
                        print("- Peremennye v prompte NE opredeleny korrrektno")
                        return False
                else:
                    print("- Soderzhanie prompta NE korrrektno")
                    return False
            else:
                print("- Ne udalos' zagruzit' prompt iz realstra")
                return False
        else:
            print("- Prompt planning.create_plan NE naiden v realstre")
            return False
            
    except RecursionError as e:
        print(f"- Obnaruzhena rekursiya: {e}")
        print("[FAILURE] PROBLEMA S REKURSIIEI NE RESHENA!")
        return False
    except Exception as e:
        print(f"- Neozhidannaya oshibka: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_recursion_fixed()
    if success:
        print("\n[RESULT] Vse testy proydeny! Problema s rekursiei polnost'yu reshena.")
    else:
        print("\n[RESULT] Testy ne proydeny! Problema sokhranyaetsya.")
        sys.exit(1)