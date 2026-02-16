#!/usr/bin/env python3
"""
Скрипт для создания правильной структуры папки data с тестовыми файлами.
"""
import os
import shutil
from pathlib import Path
import yaml

def create_test_data_structure():
    """Создание правильной структуры папки data с тестовыми файлами."""
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Загрузим registry.yaml для получения информации о типах
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создаем новую структуру папок
    new_structure = {
        'prompts': ['skill', 'tool', 'service', 'behavior'],
        'contracts': ['skill', 'tool', 'service', 'behavior']
    }
    
    for parent_dir, subdirs in new_structure.items():
        parent_path = data_dir / parent_dir
        parent_path.mkdir(exist_ok=True)
        
        for subdir in subdirs:
            # Создаем подкаталоги для каждого типа
            (parent_path / subdir).mkdir(exist_ok=True)
            
            # В каждом подкаталоге создаем подкаталоги для capability_base
            for capability, comp_type in capability_types.items():
                if comp_type == subdir:
                    cap_parts = capability.split('.')
                    if len(cap_parts) >= 2:
                        cap_main = cap_parts[0]
                        (parent_path / subdir / cap_main).mkdir(exist_ok=True)
    
    print("[INFO] Создана новая структура папок")
    
    # Создаем тестовые файлы для основных capability
    test_capabilities = [
        'planning.create_plan',
        'book_library.search_books', 
        'sql_generation.generate_query',
        'behavior.planning',
        'behavior.react'
    ]
    
    # Создаем тестовые промпты
    for capability in test_capabilities:
        if capability in capability_types:
            comp_type = capability_types[capability]
            cap_parts = capability.split('.')
            if len(cap_parts) >= 2:
                cap_main = cap_parts[0]
                
                # Создаем тестовый файл промпта
                prompt_dir = data_dir / 'prompts' / comp_type / cap_main
                prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
                
                prompt_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'content': f'Test prompt for {{{"test_var"}}}',  # Используем переменную в шаблоне
                    'variables': [
                        {
                            'name': 'test_var',
                            'description': 'Test variable',
                            'required': True
                        }
                    ],
                    'metadata': {
                        'description': f'Test prompt for {capability}',
                        'author': 'system',
                        'created': '2026-02-15'
                    }
                }
                
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    yaml.dump(prompt_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан тестовый промпт: {prompt_file}")
    
    # Создаем тестовые контракты
    for capability in test_capabilities:
        if capability in capability_types:
            comp_type = capability_types[capability]
            cap_parts = capability.split('.')
            if len(cap_parts) >= 2:
                cap_main = cap_parts[0]
                
                # Создаем тестовые файлы контрактов (input и output)
                contract_dir = data_dir / 'contracts' / comp_type / cap_main
                
                for direction in ['input', 'output']:
                    contract_file = contract_dir / f"{capability}_{direction}_v1.0.0.yaml"
                    
                    contract_content = {
                        'capability': capability,
                        'version': 'v1.0.0',
                        'status': 'active',
                        'component_type': comp_type,
                        'direction': direction,
                        'schema_data': {
                            'type': 'object',
                            'properties': {
                                'test_field': {
                                    'type': 'string',
                                    'description': f'Test field for {direction}'
                                }
                            },
                            'required': ['test_field'] if direction == 'input' else []
                        },
                        'description': f'{direction.capitalize()} contract for {capability}'
                    }
                    
                    with open(contract_file, 'w', encoding='utf-8') as f:
                        yaml.dump(contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[INFO] Создан тестовый контракт: {contract_file}")
    
    print("[SUCCESS] Создание правильной структуры папки data с тестовыми файлами завершено!")


def verify_test_structure():
    """Проверка структуры тестовых файлов."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка структуры тестовых файлов:")
    
    for parent_dir in ['prompts', 'contracts']:
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            print(f"\n  {parent_dir}/:")
            for type_dir in parent_path.iterdir():
                if type_dir.is_dir():
                    print(f"    {type_dir.name}/:")
                    for cap_dir in type_dir.iterdir():
                        if cap_dir.is_dir():
                            files = list(cap_dir.glob("*.yaml"))
                            if files:  # Показываем только папки с файлами
                                print(f"      {cap_dir.name}/: {len(files)} файлов")
                                for i, file in enumerate(files[:5]):  # Показываем первые 5 файлов
                                    print(f"        - {file.name}")
                                if len(files) > 5:
                                    print(f"        ... и еще {len(files) - 5} файлов")


if __name__ == "__main__":
    print("Начинаем создание правильной структуры папки data с тестовыми файлами...")
    create_test_data_structure()
    verify_test_structure()
    print("\n[SUCCESS] Создание правильной структуры папки data с тестовыми файлами завершено!")