#!/usr/bin/env python3
"""
Скрипт для обновления registry.yaml с добавлением capability_types.
"""
import yaml
from pathlib import Path

def update_registry_with_capability_types():
    """Обновление registry.yaml с добавлением capability_types."""
    
    # Загрузка текущего registry.yaml
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    print("[INFO] Загружен текущий registry.yaml")
    
    # Создание маппинга capability -> тип на основе компонентов
    capability_types = {}
    
    # Эвристика для определения типов
    heuristic_map = {
        'planning.': 'skill',
        'analysis.': 'skill',
        'reasoning.': 'skill',
        'sql_generation.': 'tool',
        'file_tool.': 'tool',
        'book_library.': 'tool',
        'llm.': 'service',
        'embedding.': 'service',
        'react.': 'behavior',
        'planning_pattern.': 'behavior',
        'behavior.': 'behavior'
    }
    
    # Собираем все capability из компонентных конфигураций
    sections = ['services', 'skills', 'tools', 'strategies', 'behaviors']
    
    for section in sections:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Проверяем prompt versions
                    if 'prompt_versions' in comp_config:
                        for cap in comp_config['prompt_versions'].keys():
                            capability_types[cap] = section.rstrip('s')  # skill, tool, service, behavior, strategy
                            
                    # Проверяем input contract versions
                    if 'input_contract_versions' in comp_config:
                        for cap_dir in comp_config['input_contract_versions'].keys():
                            cap = cap_dir.rsplit('.', 1)[0]
                            capability_types[cap] = section.rstrip('s')
                            
                    # Проверяем output contract versions
                    if 'output_contract_versions' in comp_config:
                        for cap_dir in comp_config['output_contract_versions'].keys():
                            cap = cap_dir.rsplit('.', 1)[0]
                            capability_types[cap] = section.rstrip('s')

    # Применяем эвристику для оставшихся capability
    for cap in capability_types:
        if capability_types[cap] == 'strategie':  # Fix plural form
            capability_types[cap] = 'strategy'
        
        # Apply heuristic if still not properly mapped
        matched = False
        for prefix, comp_type in heuristic_map.items():
            if cap.startswith(prefix):
                capability_types[cap] = comp_type
                matched = True
                break
        if not matched and capability_types[cap] == cap:  # If it was mapped to itself somehow
            # Default to skill if no match found
            capability_types[cap] = 'skill'
            print(f"[WARN] Предположен тип 'skill' для capability '{cap}'. Проверьте и исправьте вручную!")

    # Добавляем capability_types в registry_data
    registry_data['capability_types'] = capability_types
    
    # Сохраняем обновленный registry.yaml
    backup_path = Path("registry.yaml.backup")
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[INFO] Обновлен {registry_path}")
    print(f"[INFO] Добавлено типов компонентов: {len(capability_types)}")
    
    print("\n[INFO] Типы компонентов:")
    for cap, typ in sorted(capability_types.items()):
        print(f"  {cap}: {typ}")


if __name__ == "__main__":
    update_registry_with_capability_types()
    print("\n[SUCCESS] Регистр обновлен с явными типами компонентов!")