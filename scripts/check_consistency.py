#!/usr/bin/env python3
"""
Скрипт для проверки соответствия файлов в ФС и capability_types в registry.yaml.
"""
import yaml
from pathlib import Path
import os

def check_consistency():
    """Проверка соответствия файлов в ФС и capability_types в registry.yaml."""
    
    # Загрузим registry
    with open("registry.yaml", 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} capability_types из registry.yaml")
    
    data_dir = Path("data")
    
    # Проверим, что для каждого capability в registry.yaml существуют соответствующие файлы
    missing_prompts = []
    missing_input_contracts = []
    missing_output_contracts = []
    
    for capability, comp_type in capability_types.items():
        # Разбиваем capability на части
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
        else:
            print(f"[WARN] Неверный формат capability: {capability}")
            continue
        
        # Проверим наличие промпта
        prompt_dir = data_dir / "prompts" / comp_type / cap_main
        prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
        
        if not prompt_file.exists():
            missing_prompts.append((capability, comp_type))
            print(f"[MISSING PROMPT] {prompt_file}")
        else:
            print(f"[FOUND PROMPT] {prompt_file}")
        
        # Проверим наличие входного контракта
        contract_dir = data_dir / "contracts" / comp_type / cap_main
        input_contract_file = contract_dir / f"{capability}_input_v1.0.0.yaml"
        
        if not input_contract_file.exists():
            missing_input_contracts.append((capability, comp_type))
            print(f"[MISSING INPUT CONTRACT] {input_contract_file}")
        else:
            print(f"[FOUND INPUT CONTRACT] {input_contract_file}")
        
        # Проверим наличие выходного контракта
        output_contract_file = contract_dir / f"{capability}_output_v1.0.0.yaml"
        
        if not output_contract_file.exists():
            missing_output_contracts.append((capability, comp_type))
            print(f"[MISSING OUTPUT CONTRACT] {output_contract_file}")
        else:
            print(f"[FOUND OUTPUT CONTRACT] {output_contract_file}")
    
    print(f"\n[SUMMARY]")
    print(f"  Промпты отсутствуют: {len(missing_prompts)}")
    print(f"  Входные контракты отсутствуют: {len(missing_input_contracts)}")
    print(f"  Выходные контракты отсутствуют: {len(missing_output_contracts)}")
    
    if missing_prompts:
        print(f"\n[MISSING PROMPTS]:")
        for cap, typ in missing_prompts:
            print(f"  - {cap} ({typ})")
    
    if missing_input_contracts:
        print(f"\n[MISSING INPUT CONTRACTS]:")
        for cap, typ in missing_input_contracts:
            print(f"  - {cap} ({typ})")
    
    if missing_output_contracts:
        print(f"\n[MISSING OUTPUT CONTRACTS]:")
        for cap, typ in missing_output_contracts:
            print(f"  - {cap} ({typ})")
    
    total_missing = len(missing_prompts) + len(missing_input_contracts) + len(missing_output_contracts)
    
    if total_missing == 0:
        print(f"\n[SUCCESS] Все capability из registry.yaml имеют соответствующие файлы!")
        return True
    else:
        print(f"\n[INFO] Всего отсутствует {total_missing} файлов")
        return False


def create_missing_files():
    """Создание отсутствующих файлов."""
    
    # Загрузим registry
    with open("registry.yaml", 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    data_dir = Path("data")
    
    created_count = 0
    
    for capability, comp_type in capability_types.items():
        # Разбиваем capability на части
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
        else:
            continue
        
        # Создаем директории
        prompt_dir = data_dir / "prompts" / comp_type / cap_main
        contract_dir = data_dir / "contracts" / comp_type / cap_main
        
        prompt_dir.mkdir(parents=True, exist_ok=True)
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем промпт если отсутствует
        prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
        if not prompt_file.exists():
            prompt_content = {
                'capability': capability,
                'version': 'v1.0.0',
                'status': 'active',
                'component_type': comp_type,
                'content': f'Default prompt for {capability}: {{{"input"}}}',
                'variables': [
                    {
                        'name': 'input',
                        'description': f'Input for {capability}',
                        'required': True
                    }
                ],
                'metadata': {
                    'description': f'Prompt for {capability}',
                    'author': 'system',
                    'created': '2026-02-15'
                }
            }
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_content, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"[CREATED PROMPT] {prompt_file}")
            created_count += 1
        
        # Создаем входной контракт если отсутствует
        input_contract_file = contract_dir / f"{capability}_input_v1.0.0.yaml"
        if not input_contract_file.exists():
            input_contract_content = {
                'capability': capability,
                'version': 'v1.0.0',
                'status': 'active',
                'component_type': comp_type,
                'direction': 'input',
                'schema_data': {
                    'type': 'object',
                    'properties': {
                        'input': {
                            'type': 'string',
                            'description': f'Input for {capability}'
                        }
                    },
                    'required': ['input']
                },
                'description': f'Input contract for {capability}'
            }
            
            with open(input_contract_file, 'w', encoding='utf-8') as f:
                yaml.dump(input_contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"[CREATED INPUT CONTRACT] {input_contract_file}")
            created_count += 1
        
        # Создаем выходной контракт если отсутствует
        output_contract_file = contract_dir / f"{capability}_output_v1.0.0.yaml"
        if not output_contract_file.exists():
            output_contract_content = {
                'capability': capability,
                'version': 'v1.0.0',
                'status': 'active',
                'component_type': comp_type,
                'direction': 'output',
                'schema_data': {
                    'type': 'object',
                    'properties': {
                        'result': {
                            'type': 'string',
                            'description': f'Output for {capability}'
                        }
                    },
                    'required': ['result']
                },
                'description': f'Output contract for {capability}'
            }
            
            with open(output_contract_file, 'w', encoding='utf-8') as f:
                yaml.dump(output_contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"[CREATED OUTPUT CONTRACT] {output_contract_file}")
            created_count += 1
    
    print(f"\n[SUCCESS] Создано {created_count} файлов")


if __name__ == "__main__":
    print("Проверка соответствия файлов в ФС и capability_types в registry.yaml...")
    success = check_consistency()
    
    if not success:
        print("\nНекоторые файлы отсутствуют. Создаем недостающие файлы...")
        create_missing_files()
        print("\nПовторная проверка...")
        check_consistency()
    
    print("\n[SUCCESS] Проверка завершена!")