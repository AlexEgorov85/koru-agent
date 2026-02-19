#!/usr/bin/env python3
"""
РЎРєСЂРёРїС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ С„Р°Р№Р»РѕРІ РІ Р¤РЎ Рё capability_types РІ registry.yaml.
"""
import yaml
from pathlib import Path
import os

def check_consistency():
    """РџСЂРѕРІРµСЂРєР° СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ С„Р°Р№Р»РѕРІ РІ Р¤РЎ Рё capability_types РІ registry.yaml."""
    
    # Р—Р°РіСЂСѓР·РёРј registry
    with open("registry.yaml", 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Р—Р°РіСЂСѓР¶РµРЅРѕ {len(capability_types)} capability_types РёР· registry.yaml")
    
    data_dir = Path("data")
    
    # РџСЂРѕРІРµСЂРёРј, С‡С‚Рѕ РґР»СЏ РєР°Р¶РґРѕРіРѕ capability РІ registry.yaml СЃСѓС‰РµСЃС‚РІСѓСЋС‚ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РёРµ С„Р°Р№Р»С‹
    missing_prompts = []
    missing_input_contracts = []
    missing_output_contracts = []
    
    for capability, comp_type in capability_types.items():
        # Р Р°Р·Р±РёРІР°РµРј capability РЅР° С‡Р°СЃС‚Рё
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
        else:
            print(f"[WARN] РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ capability: {capability}")
            continue
        
        # РџСЂРѕРІРµСЂРёРј РЅР°Р»РёС‡РёРµ РїСЂРѕРјРїС‚Р°
        prompt_dir = data_dir / "prompts" / comp_type / cap_main
        prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
        
        if not prompt_file.exists():
            missing_prompts.append((capability, comp_type))
            print(f"[MISSING PROMPT] {prompt_file}")
        else:
            print(f"[FOUND PROMPT] {prompt_file}")
        
        # РџСЂРѕРІРµСЂРёРј РЅР°Р»РёС‡РёРµ РІС…РѕРґРЅРѕРіРѕ РєРѕРЅС‚СЂР°РєС‚Р°
        contract_dir = data_dir / "contracts" / comp_type / cap_main
        input_contract_file = contract_dir / f"{capability}_input_v1.0.0.yaml"
        
        if not input_contract_file.exists():
            missing_input_contracts.append((capability, comp_type))
            print(f"[MISSING INPUT CONTRACT] {input_contract_file}")
        else:
            print(f"[FOUND INPUT CONTRACT] {input_contract_file}")
        
        # РџСЂРѕРІРµСЂРёРј РЅР°Р»РёС‡РёРµ РІС‹С…РѕРґРЅРѕРіРѕ РєРѕРЅС‚СЂР°РєС‚Р°
        output_contract_file = contract_dir / f"{capability}_output_v1.0.0.yaml"
        
        if not output_contract_file.exists():
            missing_output_contracts.append((capability, comp_type))
            print(f"[MISSING OUTPUT CONTRACT] {output_contract_file}")
        else:
            print(f"[FOUND OUTPUT CONTRACT] {output_contract_file}")
    
    print(f"\n[SUMMARY]")
    print(f"  РџСЂРѕРјРїС‚С‹ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚: {len(missing_prompts)}")
    print(f"  Р’С…РѕРґРЅС‹Рµ РєРѕРЅС‚СЂР°РєС‚С‹ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚: {len(missing_input_contracts)}")
    print(f"  Р’С‹С…РѕРґРЅС‹Рµ РєРѕРЅС‚СЂР°РєС‚С‹ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚: {len(missing_output_contracts)}")
    
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
        print(f"\n[SUCCESS] Р’СЃРµ capability РёР· registry.yaml РёРјРµСЋС‚ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РёРµ С„Р°Р№Р»С‹!")
        return True
    else:
        print(f"\n[INFO] Р’СЃРµРіРѕ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ {total_missing} С„Р°Р№Р»РѕРІ")
        return False


def create_missing_files():
    """РЎРѕР·РґР°РЅРёРµ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‰РёС… С„Р°Р№Р»РѕРІ."""
    
    # Р—Р°РіСЂСѓР·РёРј registry
    with open("registry.yaml", 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    data_dir = Path("data")
    
    created_count = 0
    
    for capability, comp_type in capability_types.items():
        # Р Р°Р·Р±РёРІР°РµРј capability РЅР° С‡Р°СЃС‚Рё
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
        else:
            continue
        
        # РЎРѕР·РґР°РµРј РґРёСЂРµРєС‚РѕСЂРёРё
        prompt_dir = data_dir / "prompts" / comp_type / cap_main
        contract_dir = data_dir / "contracts" / comp_type / cap_main
        
        prompt_dir.mkdir(parents=True, exist_ok=True)
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        # РЎРѕР·РґР°РµРј РїСЂРѕРјРїС‚ РµСЃР»Рё РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚
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
        
        # РЎРѕР·РґР°РµРј РІС…РѕРґРЅРѕР№ РєРѕРЅС‚СЂР°РєС‚ РµСЃР»Рё РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚
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
        
        # РЎРѕР·РґР°РµРј РІС‹С…РѕРґРЅРѕР№ РєРѕРЅС‚СЂР°РєС‚ РµСЃР»Рё РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚
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
    
    print(f"\n[SUCCESS] РЎРѕР·РґР°РЅРѕ {created_count} С„Р°Р№Р»РѕРІ")


if __name__ == "__main__":
    print("РџСЂРѕРІРµСЂРєР° СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ С„Р°Р№Р»РѕРІ РІ Р¤РЎ Рё capability_types РІ registry.yaml...")
    success = check_consistency()
    
    if not success:
        print("\nРќРµРєРѕС‚РѕСЂС‹Рµ С„Р°Р№Р»С‹ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚. РЎРѕР·РґР°РµРј РЅРµРґРѕСЃС‚Р°СЋС‰РёРµ С„Р°Р№Р»С‹...")
        create_missing_files()
        print("\nРџРѕРІС‚РѕСЂРЅР°СЏ РїСЂРѕРІРµСЂРєР°...")
        check_consistency()
    
    print("\n[SUCCESS] РџСЂРѕРІРµСЂРєР° Р·Р°РІРµСЂС€РµРЅР°!")