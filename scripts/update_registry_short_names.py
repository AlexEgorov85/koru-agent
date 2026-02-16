#!/usr/bin/env python3
"""
Скрипт для обновления capability_types в registry.yaml с добавлением сокращенных имен.
"""
import yaml
from pathlib import Path

def update_registry_with_short_names():
    """Обновление capability_types в registry.yaml с добавлением сокращенных имен."""
    
    registry_path = Path("registry.yaml")
    
    # Загрузим registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Исходное количество capability_types: {len(capability_types)}")
    
    # Соберем все имена из компонентных конфигураций
    all_capabilities_from_components = set()
    
    for section in ['services', 'skills', 'tools', 'strategies', 'behaviors']:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Собираем capability из prompt_versions
                    for cap in comp_config.get('prompt_versions', {}).keys():
                        all_capabilities_from_components.add(cap)
                        # Если capability содержит точку, добавим базовую часть
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            all_capabilities_from_components.add(base_cap)
                    
                    # Собираем capability из input_contract_versions
                    for cap_dir in comp_config.get('input_contract_versions', {}).keys():
                        # Для контрактов имя может быть в формате "capability.direction"
                        cap = cap_dir.rsplit('.', 1)[0]  # Убираем направление
                        all_capabilities_from_components.add(cap)
                        # Если capability содержит точку, добавим базовую часть
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            all_capabilities_from_components.add(base_cap)
                    
                    # Собираем capability из output_contract_versions
                    for cap_dir in comp_config.get('output_contract_versions', {}).keys():
                        cap = cap_dir.rsplit('.', 1)[0]  # Убираем направление
                        all_capabilities_from_components.add(cap)
                        # Если capability содержит точку, добавим базовую часть
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            all_capabilities_from_components.add(base_cap)
    
    print(f"[INFO] Найдено {len(all_capabilities_from_components)} capability в компонентных конфигурациях")
    
    # Определим типы для сокращенных имен на основе эвристики
    heuristic_map = {
        'planning': 'skill',
        'book_library': 'tool',
        'book_library_dynamic_sql': 'tool',
        'book_library_get_full_text': 'tool',
        'book_library_search_by_author': 'tool',
        'sql_generation': 'service',
        'sql_generation_generate': 'service',
        'sql_query': 'service',
        'llm': 'service',
        'embedding': 'service',
        'react': 'behavior',
        'reasoning': 'skill',
        'analysis': 'skill',
        'behavior': 'behavior',
        'final_answer': 'skill'
    }
    
    # Добавим недостающие сокращенные имена
    added_count = 0
    for cap in all_capabilities_from_components:
        if cap not in capability_types:
            # Попробуем определить тип по эвристике
            matched = False
            for prefix, comp_type in heuristic_map.items():
                if cap.startswith(prefix):
                    capability_types[cap] = comp_type
                    print(f"[INFO] Добавлено capability '{cap}' как тип '{comp_type}' (по эвристике)")
                    matched = True
                    added_count += 1
                    break
            
            if not matched:
                # Если не удалось определить по эвристике, используем 'skill' по умолчанию
                capability_types[cap] = 'skill'
                print(f"[WARN] Добавлено capability '{cap}' как тип 'skill' (по умолчанию)")
                added_count += 1
    
    # Обновим registry_data
    registry_data['capability_types'] = capability_types
    
    # Создадим резервную копию
    backup_path = Path("registry.yaml.backup.final")
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    # Сохраним обновленный файл
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] Обновлено {added_count} capability_types. Всего теперь: {len(capability_types)}")
    
    print("\n[INFO] Некоторые из добавленных типов:")
    added_caps = list(capability_types.keys())[-10:]  # Показываем последние 10
    for cap in added_caps:
        print(f"  {cap}: {capability_types[cap]}")


def verify_updates():
    """Проверка обновлений."""
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"\n[INFO] Проверка: всего capability_types после обновления: {len(capability_types)}")
    
    # Проверим наличие проблемных capability из предупреждений
    problematic_caps = [
        'sql_generation',
        'book_library', 
        'planning',
        'behavior'
    ]
    
    for cap in problematic_caps:
        if cap in capability_types:
            print(f"[SUCCESS] Сокращенное capability '{cap}' найдено в registry: {capability_types[cap]}")
        else:
            print(f"[ERROR] Сокращенное capability '{cap}' НЕ найдено в registry")


if __name__ == "__main__":
    print("Начинаем обновление capability_types в registry.yaml...")
    update_registry_with_short_names()
    verify_updates()
    print("\n[SUCCESS] Обновление registry.yaml завершено!")