#!/usr/bin/env python3
"""
Скрипт для исправления registry.yaml - удаление сокращенных имен capability.
"""
import yaml
from pathlib import Path

def fix_registry_yaml():
    """Исправление registry.yaml - удаление сокращенных имен capability."""
    
    registry_path = Path("registry.yaml")
    
    # Загрузим registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Исходное количество capability_types: {len(capability_types)}")
    
    # Найдем capability без точки (сокращенные имена)
    short_capabilities = []
    for cap in list(capability_types.keys()):  # Используем list() чтобы избежать изменения словаря во время итерации
        if '.' not in cap:
            short_capabilities.append(cap)
    
    print(f"[INFO] Найдено {len(short_capabilities)} сокращенных имен:")
    for cap in short_capabilities:
        print(f"  - {cap}: {capability_types[cap]}")
    
    # Удалим сокращенные имена
    for cap in short_capabilities:
        del capability_types[cap]
        print(f"[REMOVED] Удалено сокращенное имя: {cap}")
    
    print(f"[INFO] Осталось {len(capability_types)} capability_types после удаления сокращенных имен")
    
    # Создадим резервную копию
    backup_path = Path("registry.yaml.backup.fixed")
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    # Сохраним обновленный файл
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] registry.yaml обновлен. Удалено {len(short_capabilities)} сокращенных имен.")
    
    print("\n[INFO] Оставшиеся capability_types:")
    for cap, typ in sorted(capability_types.items()):
        print(f"  {cap}: {typ}")


def verify_fix():
    """Проверка исправления."""
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"\n[INFO] Проверка после исправления:")
    print(f"  Всего capability_types: {len(capability_types)}")
    
    no_dot_caps = [cap for cap in capability_types.keys() if '.' not in cap]
    if no_dot_caps:
        print(f"  [ERROR] Найдены capability без точки: {no_dot_caps}")
        return False
    else:
        print(f"  [SUCCESS] Все capability содержат точку (в формате category.name)")
        return True


if __name__ == "__main__":
    print("Начинаем исправление registry.yaml...")
    fix_registry_yaml()
    success = verify_fix()
    
    if success:
        print("\n[SUCCESS] registry.yaml успешно исправлен!")
    else:
        print("\n[ERROR] registry.yaml содержит ошибки!")