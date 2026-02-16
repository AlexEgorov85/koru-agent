#!/usr/bin/env python3
"""
Скрипт для обновления registry.yaml с заменой сокращенных имен capability на полные.
"""
import yaml
from pathlib import Path

def update_registry_configurations():
    """Обновление компонентных конфигураций в registry.yaml с полными именами capability."""
    
    registry_path = Path("registry.yaml")
    backup_path = Path("registry.yaml.backup.before_update")
    
    # Создадим резервную копию
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    # Загрузим registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создадим маппинг сокращенных имен к полным
    short_to_full = {}
    for full_cap in capability_types.keys():
        if '.' in full_cap:
            parts = full_cap.split('.')
            if len(parts) >= 2:
                short_name = parts[0]  # Например, 'planning' из 'planning.create_plan'
                if short_name not in short_to_full or len(full_cap) < len(short_to_full[short_name]):
                    # Если короткое имя уже есть, сохраняем наиболее подходящее полное имя
                    # В данном случае выбираем первое найденное
                    if short_name not in short_to_full:
                        short_to_full[short_name] = full_cap
    
    # Также добавим более специфичные маппинги
    specific_mappings = {
        'sql_generation': 'sql_generation.generate_query',
        'book_library': 'book_library.search_books',
        'planning': 'planning.create_plan',
        'behavior': 'behavior.planning',
        'react': 'behavior.react'
    }
    
    # Обновим маппинг специфичными значениями
    for short, full in specific_mappings.items():
        if full in capability_types:
            short_to_full[short] = full
    
    print("[INFO] Маппинг сокращенных имен к полным:")
    for short, full in short_to_full.items():
        print(f"  {short} -> {full}")
    
    # Обновим компонентные конфигурации
    sections = ['services', 'skills', 'tools', 'strategies', 'behaviors']
    updates_count = 0
    
    for section in sections:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Обновим prompt_versions
                    if 'prompt_versions' in comp_config:
                        updated_prompt_versions = {}
                        for cap, ver in comp_config['prompt_versions'].items():
                            if cap in short_to_full:
                                new_cap = short_to_full[cap]
                                updated_prompt_versions[new_cap] = ver
                                print(f"[UPDATE] {section}.{comp_name}.prompt_versions: {cap} -> {new_cap}")
                                updates_count += 1
                            else:
                                updated_prompt_versions[cap] = ver  # Оставляем как есть
                        comp_config['prompt_versions'] = updated_prompt_versions
                    
                    # Обновим input_contract_versions
                    if 'input_contract_versions' in comp_config:
                        updated_input_contracts = {}
                        for cap_dir, ver in comp_config['input_contract_versions'].items():
                            # Извлекаем capability из имени директории
                            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                            if cap in short_to_full:
                                new_cap = short_to_full[cap]
                                new_cap_dir = f"{new_cap}.input"
                                updated_input_contracts[new_cap_dir] = ver
                                print(f"[UPDATE] {section}.{comp_name}.input_contract_versions: {cap_dir} -> {new_cap_dir}")
                                updates_count += 1
                            else:
                                updated_input_contracts[cap_dir] = ver  # Оставляем как есть
                        comp_config['input_contract_versions'] = updated_input_contracts
                    
                    # Обновим output_contract_versions
                    if 'output_contract_versions' in comp_config:
                        updated_output_contracts = {}
                        for cap_dir, ver in comp_config['output_contract_versions'].items():
                            # Извлекаем capability из имени директории
                            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
                            if cap in short_to_full:
                                new_cap = short_to_full[cap]
                                new_cap_dir = f"{new_cap}.output"
                                updated_output_contracts[new_cap_dir] = ver
                                print(f"[UPDATE] {section}.{comp_name}.output_contract_versions: {cap_dir} -> {new_cap_dir}")
                                updates_count += 1
                            else:
                                updated_output_contracts[cap_dir] = ver  # Оставляем как есть
                        comp_config['output_contract_versions'] = updated_output_contracts
    
    # Также обновим active_prompts и active_contracts если они есть
    if 'active_prompts' in registry_data:
        updated_active_prompts = {}
        for cap, ver in registry_data['active_prompts'].items():
            if cap in short_to_full:
                new_cap = short_to_full[cap]
                updated_active_prompts[new_cap] = ver
                print(f"[UPDATE] active_prompts: {cap} -> {new_cap}")
                updates_count += 1
            else:
                updated_active_prompts[cap] = ver
        registry_data['active_prompts'] = updated_active_prompts
    
    if 'active_contracts' in registry_data:
        updated_active_contracts = {}
        for cap_dir, ver in registry_data['active_contracts'].items():
            cap = cap_dir.rsplit('.', 1)[0] if '.' in cap_dir else cap_dir
            if cap in short_to_full:
                new_cap = short_to_full[cap]
                direction = cap_dir.rsplit('.', 1)[1] if '.' in cap_dir else 'input'  # предполагаем input по умолчанию
                new_cap_dir = f"{new_cap}.{direction}"
                updated_active_contracts[new_cap_dir] = ver
                print(f"[UPDATE] active_contracts: {cap_dir} -> {new_cap_dir}")
                updates_count += 1
            else:
                updated_active_contracts[cap_dir] = ver
        registry_data['active_contracts'] = updated_active_contracts
    
    # Сохраним обновленный registry.yaml
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[SUCCESS] Обновлено {updates_count} записей в registry.yaml")
    
    # Проверим обновленный файл
    print("\n[INFO] Обновленные компонентные конфигурации:")
    for section in sections:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    if 'prompt_versions' in comp_config and comp_config['prompt_versions']:
                        print(f"  {section}.{comp_name}.prompt_versions: {comp_config['prompt_versions']}")
                    if 'input_contract_versions' in comp_config and comp_config['input_contract_versions']:
                        print(f"  {section}.{comp_name}.input_contract_versions: {comp_config['input_contract_versions']}")
                    if 'output_contract_versions' in comp_config and comp_config['output_contract_versions']:
                        print(f"  {section}.{comp_name}.output_contract_versions: {comp_config['output_contract_versions']}")


def verify_updates():
    """Проверка обновлений."""
    registry_path = Path("registry.yaml")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    print("\n[INFO] Проверка обновлений в registry.yaml:")
    
    # Проверим несколько ключевых компонентов
    key_components = [
        ('services', 'sql_generation_service'),
        ('skills', 'planning'),
        ('tools', 'book_library'),
        ('behaviors', 'react_pattern')
    ]
    
    for section, comp_name in key_components:
        if section in registry_data and comp_name in registry_data[section]:
            comp_config = registry_data[section][comp_name]
            if isinstance(comp_config, dict):
                print(f"\n  {section}.{comp_name}:")
                if 'prompt_versions' in comp_config:
                    print(f"    prompt_versions: {comp_config['prompt_versions']}")
                if 'input_contract_versions' in comp_config:
                    print(f"    input_contract_versions: {comp_config['input_contract_versions']}")
                if 'output_contract_versions' in comp_config:
                    print(f"    output_contract_versions: {comp_config['output_contract_versions']}")


if __name__ == "__main__":
    print("Начинаем обновление registry.yaml с полными именами capability...")
    update_registry_configurations()
    verify_updates()
    print("\n[SUCCESS] Обновление registry.yaml завершено!")