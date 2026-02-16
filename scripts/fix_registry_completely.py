#!/usr/bin/env python3
"""
Скрипт для полного исправления registry.yaml с учетом новой архитектуры.
"""
import yaml
from pathlib import Path

def fix_registry_completely():
    """Полное исправление registry.yaml для новой архитектуры."""
    
    registry_path = Path("registry.yaml")
    backup_path = Path("registry.yaml.backup.complete_fix")
    
    # Загрузим registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создадим резервную копию
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    # Обновим компонентные конфигурации, чтобы они соответствовали новой архитектуре
    sections = ['services', 'skills', 'tools', 'strategies', 'behaviors']
    
    for section in sections:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Обновим prompt_versions
                    if 'prompt_versions' in comp_config:
                        updated_prompts = {}
                        for cap, ver in comp_config['prompt_versions'].items():
                            # Проверим, есть ли такое capability в capability_types
                            if cap in capability_types:
                                updated_prompts[cap] = ver
                                print(f"[INFO] Сохранено: {section}.{comp_name}.prompt_versions.{cap} = {ver}")
                            else:
                                print(f"[WARN] Удалено (нет в capability_types): {cap}")
                        registry_data[section][comp_name]['prompt_versions'] = updated_prompts
                    
                    # Обновим input_contract_versions
                    if 'input_contract_versions' in comp_config:
                        updated_inputs = {}
                        for cap_dir, ver in comp_config['input_contract_versions'].items():
                            # Извлекаем capability из имени директории
                            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                            if cap in capability_types:
                                updated_inputs[cap_dir] = ver
                                print(f"[INFO] Сохранено: {section}.{comp_name}.input_contract_versions.{cap_dir} = {ver}")
                            else:
                                print(f"[WARN] Удалено (capability нет в capability_types): {cap_dir}")
                        registry_data[section][comp_name]['input_contract_versions'] = updated_inputs
                    
                    # Обновим output_contract_versions
                    if 'output_contract_versions' in comp_config:
                        updated_outputs = {}
                        for cap_dir, ver in comp_config['output_contract_versions'].items():
                            # Извлекаем capability из имени директории
                            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                            if cap in capability_types:
                                updated_outputs[cap_dir] = ver
                                print(f"[INFO] Сохранено: {section}.{comp_name}.output_contract_versions.{cap_dir} = {ver}")
                            else:
                                print(f"[WARN] Удалено (capability нет в capability_types): {cap_dir}")
                        registry_data[section][comp_name]['output_contract_versions'] = updated_outputs
    
    # Также обновим active_prompts и active_contracts
    if 'active_prompts' in registry_data:
        updated_active_prompts = {}
        for cap, ver in registry_data['active_prompts'].items():
            if cap in capability_types:
                updated_active_prompts[cap] = ver
                print(f"[INFO] Сохранен активный промпт: {cap} = {ver}")
            else:
                print(f"[WARN] Удален активный промпт (нет в capability_types): {cap}")
        registry_data['active_prompts'] = updated_active_prompts
    
    if 'active_contracts' in registry_data:
        updated_active_contracts = {}
        for cap_dir, ver in registry_data['active_contracts'].items():
            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
            if cap in capability_types:
                updated_active_contracts[cap_dir] = ver
                print(f"[INFO] Сохранен активный контракт: {cap_dir} = {ver}")
            else:
                print(f"[WARN] Удален активный контракт (capability нет в capability_types): {cap_dir}")
        registry_data['active_contracts'] = updated_active_contracts
    
    # Сохраним обновленный файл
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] registry.yaml полностью исправлен и обновлен!")


def add_missing_component_configs():
    """Добавление недостающих конфигураций компонентов."""
    
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    # Добавим недостающие конфигурации компонентов
    missing_components = {
        'sql_generation_service': {
            'enabled': True,
            'dependencies': ['default_db'],
            'prompt_versions': {
                'sql_generation.generate_query': 'v1.0.0'
            },
            'input_contract_versions': {
                'sql_generation.generate_query.input': 'v1.0.0'
            },
            'output_contract_versions': {
                'sql_generation.generate_query.output': 'v1.0.0'
            }
        },
        'book_library': {
            'enabled': True,
            'dependencies': ['default_db'],
            'prompt_versions': {
                'book_library.search_books': 'v1.0.0'
            },
            'input_contract_versions': {
                'book_library.search_books.input': 'v1.0.0'
            },
            'output_contract_versions': {
                'book_library.search_books.output': 'v1.0.0'
            }
        },
        'planning': {
            'enabled': True,
            'dependencies': [],
            'prompt_versions': {
                'planning.create_plan': 'v1.0.0'
            },
            'input_contract_versions': {
                'planning.create_plan.input': 'v1.0.0'
            },
            'output_contract_versions': {
                'planning.create_plan.output': 'v1.0.0'
            }
        }
    }
    
    # Убедимся, что разделы существуют
    for section in ['services', 'skills', 'tools', 'behaviors']:
        if section not in registry_data:
            registry_data[section] = {}
    
    # Добавим недостающие компоненты
    for comp_name, comp_config in missing_components.items():
        # Определим, в какой раздел добавить компонент
        if comp_name == 'sql_generation_service':
            section = 'services'
        elif comp_name == 'book_library':
            section = 'skills'  # или 'tools' в зависимости от типа
        elif comp_name == 'planning':
            section = 'skills'
        else:
            section = 'skills'  # по умолчанию
        
        # Проверим, есть ли уже такой компонент
        if comp_name not in registry_data[section]:
            # Проверим, что все capability в конфигурации существуют в capability_types
            valid_config = {}
            
            if 'prompt_versions' in comp_config:
                valid_prompts = {}
                for cap, ver in comp_config['prompt_versions'].items():
                    if cap in capability_types:
                        valid_prompts[cap] = ver
                if valid_prompts:
                    valid_config['prompt_versions'] = valid_prompts
            
            if 'input_contract_versions' in comp_config:
                valid_inputs = {}
                for cap_dir, ver in comp_config['input_contract_versions'].items():
                    cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                    if cap in capability_types:
                        valid_inputs[cap_dir] = ver
                if valid_inputs:
                    valid_config['input_contract_versions'] = valid_inputs
            
            if 'output_contract_versions' in comp_config:
                valid_outputs = {}
                for cap_dir, ver in comp_config['output_contract_versions'].items():
                    cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                    if cap in capability_types:
                        valid_outputs[cap_dir] = ver
                if valid_outputs:
                    valid_config['output_contract_versions'] = valid_outputs
            
            # Добавим остальные поля
            for key, value in comp_config.items():
                if key not in ['prompt_versions', 'input_contract_versions', 'output_contract_versions']:
                    valid_config[key] = value
            
            if valid_config:  # Только если есть валидные конфигурации
                registry_data[section][comp_name] = valid_config
                print(f"[INFO] Добавлен компонент: {section}.{comp_name}")
    
    # Сохраним обновленный файл
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] Недостающие конфигурации компонентов добавлены!")


def verify_fix():
    """Проверка исправления."""
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print("\n[INFO] Проверка исправления:")
    print(f"  capability_types: {len(capability_types)} записей")
    
    # Проверим наличие ключевых компонентов
    key_components = [
        ('services', 'sql_generation_service'),
        ('skills', 'book_library'),
        ('skills', 'planning'),
        ('behaviors', 'planning_pattern'),
        ('behaviors', 'react_pattern')
    ]
    
    for section, comp_name in key_components:
        if section in registry_data and comp_name in registry_data[section]:
            comp_config = registry_data[section][comp_name]
            print(f"  {section}.{comp_name}:")
            if 'prompt_versions' in comp_config:
                print(f"    prompt_versions: {comp_config['prompt_versions']}")
            if 'input_contract_versions' in comp_config:
                print(f"    input_contract_versions: {comp_config['input_contract_versions']}")
            if 'output_contract_versions' in comp_config:
                print(f"    output_contract_versions: {comp_config['output_contract_versions']}")
        else:
            print(f"  [MISSING] {section}.{comp_name}")


if __name__ == "__main__":
    print("Начинаем полное исправление registry.yaml...")
    fix_registry_completely()
    add_missing_component_configs()
    verify_fix()
    print("\n[SUCCESS] Полное исправление registry.yaml завершено!")