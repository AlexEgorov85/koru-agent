#!/usr/bin/env python3
"""
Проверка на дублирование конфигурации между слоями.
"""
import yaml
import sys
from pathlib import Path
from typing import List

# Поля, которые НЕ должны быть в инфраструктурной конфигурации
FORBIDDEN_IN_INFRA = [
    'agent_config',
    'prompt_versions',
    'contract_versions',
    'component_versions',
    'skill_versions',
    'tool_versions',
    'service_versions',
    'behavior_versions',
]

# Поля, которые НЕ должны быть в прикладной конфигурации
FORBIDDEN_IN_APP = [
    'llm_providers',
    'db_providers',
    'data_dir',
    'provider_type',
    'model_path',
    'connection_string',
    'database_url',
]

def check_infra_config(config_path: Path) -> List[str]:
    """Проверка инфраструктурной конфигурации."""
    errors = []
    
    if not config_path.exists():
        return [f"Файл не найден: {config_path}"]
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if config is None:
        return []
    
    config_str = str(config)
    for field in FORBIDDEN_IN_INFRA:
        if field in config_str:
            errors.append(f"❌ '{field}' не должен быть в инфраструктурной конфигурации")
    
    return errors

def check_registry_config(config_path: Path) -> List[str]:
    """Проверка прикладной конфигурации (registry.yaml)."""
    errors = []
    
    if not config_path.exists():
        return [f"Файл не найден: {config_path}"]
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if config is None:
        return []
    
    config_str = str(config)
    for field in FORBIDDEN_IN_APP:
        if field in config_str:
            errors.append(f"❌ '{field}' не должен быть в прикладной конфигурации")
    
    return errors

def main():
    all_errors = []
    
    # Проверка инфраструктурных конфигов
    infra_configs_dir = Path('core/config/defaults')
    if infra_configs_dir.exists():
        infra_configs = infra_configs_dir.glob('*.yaml')
        for config_path in infra_configs:
            errors = check_infra_config(config_path)
            all_errors.extend([f"{config_path.name}: {e}" for e in errors])
    
    # Проверка registry.yaml
    registry_path = Path('data/registry.yaml')
    errors = check_registry_config(registry_path)
    all_errors.extend([f"registry.yaml: {e}" for e in errors])
    
    if all_errors:
        print("[FAIL] ОБНАРУЖЕНО ДУБЛИРОВАНИЕ КОНФИГУРАЦИИ:")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("[PASS] Дублирование конфигурации отсутствует")
        sys.exit(0)

if __name__ == '__main__':
    main()