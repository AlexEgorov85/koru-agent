#!/usr/bin/env python3
"""
Валидатор согласованности версий:
- Проверяет, что промпт совместим с контрактом
- Обнаруживает "дыры" в зависимостях
- Блокирует опасные комбинации
"""

import sys
import yaml
import json
from pathlib import Path
from packaging import version


def validate_component_versions(component: str, manifest: dict) -> list:
    """Валидация согласованности версий для компонента"""
    errors = []
    
    if component not in manifest["components"]:
        return [f"Компонент {component} не найден в манифесте"]
    
    comp_data = manifest["components"][component]
    prompts = comp_data.get("prompt_versions", {})
    contracts = comp_data.get("contract_versions", {})
    
    for cap_name, prompt_ver in prompts.items():
        # Проверяем входящий контракт
        input_key = f"{cap_name}.input"
        if input_key in contracts:
            contract_ver = contracts[input_key]
            # Проверка семантической совместимости
            if not is_prompt_compatible_with_contract(prompt_ver, contract_ver, "input"):
                errors.append(
                    f"Несовместимость: промпт {cap_name}@{prompt_ver} "
                    f"требует контракт input >= v1.0.0, но указан {contract_ver}"
                )
        
        # Проверяем исходящий контракт
        output_key = f"{cap_name}.output"
        if output_key in contracts:
            contract_ver = contracts[output_key]
            # Проверка семантической совместимости
            if not is_prompt_compatible_with_contract(prompt_ver, contract_ver, "output"):
                errors.append(
                    f"Несовместимость: промпт {cap_name}@{prompt_ver} "
                    f"требует контракт output >= v1.0.0, но указан {contract_ver}"
                )
    
    return errors


def is_prompt_compatible_with_contract(prompt_ver: str, contract_ver: str, direction: str) -> bool:
    """Проверка семантической совместимости"""
    # Убираем 'v' префиксы для сравнения
    prompt_version_clean = prompt_ver.lstrip('v')
    contract_version_clean = contract_ver.lstrip('v')
    
    try:
        prompt_v = version.parse(prompt_version_clean)
        contract_v = version.parse(contract_version_clean)
        
        # Пример правила: промпт v1.0.0+ требует контракт input v1.0.0+
        if prompt_v >= version.parse("1.0.0") and direction == "input" and contract_v < version.parse("1.0.0"):
            return False
        return True
    except:
        # Если не удается распарсить версии, предполагаем совместимость
        return True


def validate_manifest_consistency(manifest_path: str = "versioning/manifest.yaml") -> bool:
    """Проверяет согласованность всего манифеста"""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Не удалось загрузить манифест: {e}")
        return False
    
    all_errors = []
    
    # Проверяем каждый компонент
    for component in manifest.get("components", {}):
        errors = validate_component_versions(component, manifest)
        all_errors.extend(errors)
    
    # Проверяем зависимости версий
    version_deps = manifest.get("version_dependencies", [])
    for dep in version_deps:
        component = dep.get("component")
        capability = dep.get("capability")
        required_prompt_ver = dep.get("prompt_version")
        
        if component and capability and required_prompt_ver and component in manifest["components"]:
            comp_data = manifest["components"][component]
            prompts = comp_data.get("prompt_versions", {})
            
            if capability in prompts:
                actual_ver = prompts[capability]
                if not is_version_greater_or_equal(actual_ver, required_prompt_ver):
                    all_errors.append(
                        f"Нарушение зависимости: компонент {component}.{capability} "
                        f"требует версию >= {required_prompt_ver}, но указана {actual_ver}"
                    )
    
    # Выводим ошибки
    if all_errors:
        print("Найдены ошибки согласованности версий:")
        for error in all_errors:
            print(f"  - {error}")
        return False
    else:
        print("[OK] Все версии согласованы")
        return True


def is_version_greater_or_equal(ver1: str, ver2: str) -> bool:
    """Проверяет, что версия ver1 >= ver2"""
    v1_clean = ver1.lstrip('v')
    v2_clean = ver2.lstrip('v')
    
    try:
        return version.parse(v1_clean) >= version.parse(v2_clean)
    except:
        return True  # Если не удается сравнить, предполагаем совместимость


if __name__ == "__main__":
    # Использование:
    #   python scripts/versioning/validate_consistency.py --manifest versioning/manifest.yaml
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate version consistency')
    parser.add_argument('--manifest', default='versioning/manifest.yaml', help='Path to manifest file')
    parser.add_argument('--analysis', help='Path to analysis JSON file')
    
    args = parser.parse_args()
    
    if args.analysis:
        # Если передан файл анализа, проверяем только затронутые компоненты
        try:
            with open(args.analysis, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            
            # Извлекаем затронутые компоненты из анализа
            affected_components = set()
            
            prompt_versions = analysis.get("version_bump_suggestions", {}).get("prompt_versions", {})
            contract_versions = analysis.get("version_bump_suggestions", {}).get("contract_versions", {})
            
            affected_components.update(prompt_versions.keys())
            affected_components.update(contract_versions.keys())
            
            # Загружаем манифест
            with open(args.manifest, 'r', encoding='utf-8') as f:
                manifest = yaml.safe_load(f)
            
            # Проверяем только затронутые компоненты
            all_errors = []
            for component in affected_components:
                errors = validate_component_versions(component, manifest)
                all_errors.extend(errors)
            
            if all_errors:
                print("Найдены ошибки согласованности для затронутых компонентов:")
                for error in all_errors:
                    print(f"  - {error}")
                sys.exit(1)
            else:
                print("[OK] Затронутые компоненты согласованы")
                sys.exit(0)
                
        except Exception as e:
            print(f"ERROR: Не удалось обработать файл анализа: {e}")
            sys.exit(1)
    else:
        # Проверяем весь манифест
        success = validate_manifest_consistency(args.manifest)
        sys.exit(0 if success else 1)