#!/usr/bin/env python3
"""
Скрипт для создания файлов для сокращенных имен capability, указанных в компонентных конфигурациях.
"""
import yaml
from pathlib import Path

def create_short_name_files():
    """Создание файлов для сокращенных имен capability."""
    
    registry_path = Path("registry.yaml")
    data_dir = Path("data")
    
    # Загрузим registry для получения информации о компонентах
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    # Соберем все сокращенные имена из компонентных конфигураций
    short_capabilities = set()
    
    for section in ['services', 'skills', 'tools', 'strategies', 'behaviors']:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Проверим prompt versions
                    for cap in comp_config.get('prompt_versions', {}).keys():
                        # Если capability содержит точку, добавим базовую часть
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            short_capabilities.add(base_cap)
                    
                    # Проверим input contract versions
                    for cap_dir in comp_config.get('input_contract_versions', {}).keys():
                        # Для контрактов имя может быть в формате "capability.direction"
                        cap = cap_dir.rsplit('.', 1)[0]  # Убираем направление
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            short_capabilities.add(base_cap)
                        else:
                            short_capabilities.add(cap)
                    
                    # Проверим output contract versions
                    for cap_dir in comp_config.get('output_contract_versions', {}).keys():
                        cap = cap_dir.rsplit('.', 1)[0]
                        if '.' in cap:
                            base_cap = cap.split('.')[0]
                            short_capabilities.add(base_cap)
                        else:
                            short_capabilities.add(cap)
    
    print(f"[INFO] Найдено {len(short_capabilities)} сокращенных имен capability: {short_capabilities}")
    
    # Также добавим имена, упомянутые в validation_warnings
    additional_short_caps = [
        'sql_generation', 'book_library', 'planning', 'behavior'
    ]
    for cap in additional_short_caps:
        short_capabilities.add(cap)
    
    # Определим типы для сокращенных имен (на основе эвристики)
    short_cap_types = {}
    heuristic_map = {
        'sql_generation': 'service',
        'book_library': 'tool', 
        'planning': 'skill',
        'behavior': 'behavior',
        'react': 'behavior',
        'llm': 'service',
        'embedding': 'service'
    }
    
    for cap in short_capabilities:
        matched = False
        for prefix, comp_type in heuristic_map.items():
            if cap.startswith(prefix):
                short_cap_types[cap] = comp_type
                matched = True
                break
        if not matched:
            # По умолчанию используем 'skill'
            short_cap_types[cap] = 'skill'
            print(f"[WARN] Предположен тип 'skill' для сокращенного capability '{cap}'")
    
    # Создаем файлы для сокращенных имен
    for capability, comp_type in short_cap_types.items():
        # Создаем директорию
        prompt_dir = data_dir / "prompts" / comp_type / capability
        prompt_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем файл промпта
        prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
        
        if not prompt_file.exists():  # Создаем только если файл не существует
            prompt_content = {
                'capability': capability,
                'version': 'v1.0.0',
                'status': 'active',
                'component_type': comp_type,
                'content': f'Default prompt for {capability}: {{{"input"}}}',
                'variables': [
                    {
                        'name': 'input',
                        'description': f'Main input for {capability}',
                        'required': True
                    }
                ],
                'metadata': {
                    'description': f'Default prompt for {capability}',
                    'author': 'system',
                    'created': '2026-02-15'
                }
            }
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_content, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"[INFO] Создан промпт для сокращенного capability: {prompt_file}")
        
        # Создаем файлы контрактов
        contract_dir = data_dir / "contracts" / comp_type / capability
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        for direction in ['input', 'output']:
            contract_file = contract_dir / f"{capability}_{direction}_v1.0.0.yaml"
            
            if not contract_file.exists():  # Создаем только если файл не существует
                if direction == 'input':
                    schema_properties = {
                        'input': {'type': 'string', 'description': f'Input for {capability}'}
                    }
                    required_fields = ['input']
                else:  # output
                    schema_properties = {
                        'result': {'type': 'string', 'description': f'Output for {capability}'}
                    }
                    required_fields = ['result']
                
                contract_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'direction': direction,
                    'schema_data': {
                        'type': 'object',
                        'properties': schema_properties,
                        'required': required_fields
                    },
                    'description': f'{direction.capitalize()} contract for {capability}'
                }
                
                with open(contract_file, 'w', encoding='utf-8') as f:
                    yaml.dump(contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан {direction} контракт для сокращенного capability: {contract_file}")
    
    print("[SUCCESS] Создание файлов для сокращенных имен завершено!")


if __name__ == "__main__":
    print("Начинаем создание файлов для сокращенных имен capability...")
    create_short_name_files()
    print("\n[SUCCESS] Все файлы для сокращенных имен созданы!")