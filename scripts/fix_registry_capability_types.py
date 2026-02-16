#!/usr/bin/env python3
"""
Скрипт для исправления registry.yaml - удаление неправильных имен из capability_types.
"""
import yaml
from pathlib import Path

def fix_registry_capability_types():
    """Исправление capability_types в registry.yaml."""
    
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Исходное количество capability_types: {len(capability_types)}")
    
    # Определим правильные имена (те, что должны остаться)
    # Правильные имена - те, что в формате category.name (с точкой)
    correct_capabilities = []
    incorrect_capabilities = []
    
    for cap in capability_types.keys():
        if '.' in cap:
            # Это правильное имя в формате category.name
            correct_capabilities.append(cap)
        else:
            # Это потенциально неправильное имя без точки
            incorrect_capabilities.append(cap)
    
    print(f"[INFO] Правильные имена (с точкой): {len(correct_capabilities)}")
    print(f"[INFO] Потенциально неправильные имена (без точки): {len(incorrect_capabilities)}")
    
    for cap in incorrect_capabilities:
        print(f"  - {cap}")
    
    # Создадим новый словарь capability_types только с правильными именами
    new_capability_types = {cap: capability_types[cap] for cap in correct_capabilities}
    
    print(f"[INFO] Новое количество capability_types: {len(new_capability_types)}")
    
    # Обновим registry_data
    registry_data['capability_types'] = new_capability_types
    
    # Создадим резервную копию
    backup_path = Path("registry.yaml.backup_fixed")
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    # Сохраним обновленный файл
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] registry.yaml обновлен. Удалено {len(incorrect_capabilities)} неправильных имен.")


def verify_fix():
    """Проверка исправления."""
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"\n[INFO] Проверка после исправления:")
    print(f"  Всего capability_types: {len(capability_types)}")
    
    incorrect_found = []
    for cap in capability_types.keys():
        if '.' not in cap:
            incorrect_found.append(cap)
    
    if incorrect_found:
        print(f"  [ERROR] Найдены неправильные имена (без точки): {len(incorrect_found)}")
        for cap in incorrect_found:
            print(f"    - {cap}")
    else:
        print(f"  [SUCCESS] Все имена в правильном формате (с точкой)")


if __name__ == "__main__":
    print("Начинаем исправление registry.yaml...")
    fix_registry_capability_types()
    verify_fix()
    print("\n[SUCCESS] Исправление registry.yaml завершено!")