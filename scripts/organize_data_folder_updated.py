#!/usr/bin/env python3
"""
Скрипт для реорганизации папки data в соответствии с новой архитектурой.
"""
import os
import shutil
from pathlib import Path
import yaml
import re

def organize_data_folder():
    """Реорганизация папки data в соответствии с новой архитектурой."""
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"[ERROR] Папка {data_dir} не найдена!")
        return
    
    # Загрузим registry.yaml для получения информации о типах
    registry_path = data_dir / "registry.yaml"
    if not registry_path.exists():
        # Попробуем найти registry.yaml в корне проекта
        registry_path = Path("registry.yaml")
        if not registry_path.exists():
            print(f"[ERROR] Файл registry.yaml не найден!")
            return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создаем новую структуру папок
    new_structure = {
        'prompts': ['skills', 'tools', 'services', 'behaviors'],
        'contracts': ['skills', 'tools', 'services', 'behaviors']
    }
    
    for parent_dir, subdirs in new_structure.items():
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            for subdir in subdirs:
                (parent_path / subdir).mkdir(exist_ok=True)
    
    print("[SUCCESS] Создана новая структура папок!")


def create_sample_files_for_missing_capabilities():
    """Создание образцов файлов для capability, у которых нет файлов."""
    
    data_dir = Path("data")
    # Попробуем найти registry.yaml в корне проекта
    registry_path = Path("registry.yaml")
    
    if not registry_path.exists():
        print(f"[ERROR] Файл registry.yaml не найден в корне проекта!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    # Проверяем, какие capability не имеют файлов
    prompts_dir = data_dir / "prompts"
    contracts_dir = data_dir / "contracts"
    
    for capability, comp_type in capability_types.items():
        # Проверяем наличие промпта
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
            cap_sub = cap_parts[1]
            
            # Проверяем, есть ли файлы для этого capability
            cap_prompt_dir = prompts_dir / comp_type / cap_main
            prompt_exists = any(cap_prompt_dir.glob(f"{capability}_v*.yaml")) if cap_prompt_dir.exists() else False
            
            if not prompt_exists:
                # Создаем образец файла промпта
                cap_prompt_dir.mkdir(parents=True, exist_ok=True)
                sample_prompt_file = cap_prompt_dir / f"{capability}_v1.0.0.yaml"
                
                sample_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'content': f'Sample prompt for {capability}',
                    'variables': [],
                    'metadata': {
                        'description': f'Sample prompt for {capability}',
                        'author': 'system',
                        'created': '2026-02-15'
                    }
                }
                
                with open(sample_prompt_file, 'w', encoding='utf-8') as f:
                    yaml.dump(sample_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан образец промпта: {sample_prompt_file}")
            
            # Проверяем наличие контрактов
            cap_contract_dir = contracts_dir / comp_type / cap_main
            input_contract_exists = any(cap_contract_dir.glob(f"{capability}_input_v*.yaml")) if cap_contract_dir.exists() else False
            output_contract_exists = any(cap_contract_dir.glob(f"{capability}_output_v*.yaml")) if cap_contract_dir.exists() else False
            
            if not input_contract_exists:
                # Создаем образец входного контракта
                cap_contract_dir.mkdir(parents=True, exist_ok=True)
                sample_input_contract_file = cap_contract_dir / f"{capability}_input_v1.0.0.yaml"
                
                sample_input_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'direction': 'input',
                    'schema_data': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    },
                    'description': f'Input contract for {capability}'
                }
                
                with open(sample_input_contract_file, 'w', encoding='utf-8') as f:
                    yaml.dump(sample_input_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан образец входного контракта: {sample_input_contract_file}")
            
            if not output_contract_exists:
                # Создаем образец выходного контракта
                sample_output_contract_file = cap_contract_dir / f"{capability}_output_v1.0.0.yaml"
                
                sample_output_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'direction': 'output',
                    'schema_data': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    },
                    'description': f'Output contract for {capability}'
                }
                
                with open(sample_output_contract_file, 'w', encoding='utf-8') as f:
                    yaml.dump(sample_output_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан образец выходного контракта: {sample_output_contract_file}")


if __name__ == "__main__":
    print("Начинаем подготовку новой структуры папки data...")
    organize_data_folder()
    print("\nСоздаем образцы файлов для отсутствующих capability...")
    create_sample_files_for_missing_capabilities()
    print("\n[SUCCESS] Подготовка структуры папки data завершена!")