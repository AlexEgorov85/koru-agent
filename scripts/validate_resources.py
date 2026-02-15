#!/usr/bin/env python3
"""
Скрипт для проверки наличия и целостности всех ресурсов системы.
Проверяет промты, контракты и другие ресурсы, указанные в конфигурации.
"""
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Set
import yaml
import json

# Добавляем корневую директорию проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_yaml_file(filepath: Path) -> dict:
    """Загрузка YAML файла."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"❌ Ошибка загрузки {filepath}: {e}")
        return {}


def find_resource_files(directory: Path, extensions: List[str]) -> List[Path]:
    """Поиск файлов ресурсов в директории."""
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*.{ext}"))
    return files


def validate_prompts(config: dict, data_dir: Path) -> Tuple[int, int, List[str]]:
    """Проверка наличия файлов промтов."""
    print("🔍 Проверка промтов...")
    
    prompt_versions = config.get('app_config', {}).get('prompt_versions', {})
    if not prompt_versions:
        # Проверяем также в registry.yaml
        prompt_versions = {}
        for comp_type in ['services', 'skills', 'tools']:
            components = config.get(comp_type, {})
            for comp_name, comp_config in components.items():
                comp_prompts = comp_config.get('prompt_versions', {})
                for cap, ver in comp_prompts.items():
                    prompt_versions[f"{comp_name}.{cap}"] = ver
    
    total_prompts = len(prompt_versions)
    found_prompts = 0
    missing_prompts = []
    
    prompt_dir = data_dir / "prompts"
    
    for capability, version in prompt_versions.items():
        # Разбиваем capability на части (например, planning.create_plan -> planning/create_plan)
        parts = capability.split('.')
        relative_path = "/".join(parts)
        
        # Проверяем различные возможные форматы файлов
        possible_paths = [
            prompt_dir / relative_path / f"{version}.yaml",
            prompt_dir / relative_path / f"{version}.json",
            prompt_dir / f"{relative_path}_{version}.yaml",
            prompt_dir / f"{relative_path}_{version}.json",
        ]
        
        found = False
        for path in possible_paths:
            if path.exists():
                found = True
                found_prompts += 1
                print(f"  ✅ {capability}@{version} -> {path}")
                break
        
        if not found:
            missing_prompts.append((capability, version))
            print(f"  ❌ {capability}@{version} -> файл не найден")
            # Показываем возможные пути для отладки
            for path in possible_paths:
                print(f"     - {path}")
    
    return total_prompts, found_prompts, missing_prompts


def validate_contracts(config: dict, data_dir: Path) -> Tuple[int, int, List[str]]:
    """Проверка наличия файлов контрактов."""
    print("\n🔍 Проверка контрактов...")
    
    # Собираем все версии контрактов из конфигурации
    contract_versions = {}
    
    # Из app_config
    app_config = config.get('app_config', {})
    for contract_type in ['input_contract_versions', 'output_contract_versions']:
        for capability, version in app_config.get(contract_type, {}).items():
            contract_versions[(capability, contract_type.split('_')[0])] = version
    
    # Из registry.yaml
    for comp_type in ['services', 'skills', 'tools']:
        components = config.get(comp_type, {})
        for comp_name, comp_config in components.items():
            for contract_type in ['input_contract_versions', 'output_contract_versions']:
                for capability, version in comp_config.get(contract_type, {}).items():
                    direction = 'input' if 'input' in contract_type else 'output'
                    contract_versions[(f"{comp_name}.{capability}", direction)] = version
    
    total_contracts = len(contract_versions)
    found_contracts = 0
    missing_contracts = []
    
    contract_dir = data_dir / "contracts"
    
    for (capability, direction), version in contract_versions.items():
        # Разбиваем capability на части
        parts = capability.split('.')
        relative_path = "/".join(parts)
        
        # Проверяем различные возможные форматы файлов
        possible_paths = [
            contract_dir / relative_path / f"{version}_{direction}.yaml",
            contract_dir / relative_path / f"{version}_{direction}.json",
            contract_dir / relative_path / f"{version}_{direction}.yml",
            contract_dir / f"{relative_path}_{version}_{direction}.yaml",
            contract_dir / f"{relative_path}_{version}_{direction}.json",
            contract_dir / f"{relative_path}_{version}_{direction}.yml",
        ]
        
        found = False
        for path in possible_paths:
            if path.exists():
                found = True
                found_contracts += 1
                print(f"  ✅ {capability}@{version} ({direction}) -> {path}")
                break
        
        if not found:
            missing_contracts.append((capability, version, direction))
            print(f"  ❌ {capability}@{version} ({direction}) -> файл не найден")
            # Показываем возможные пути для отладки
            for path in possible_paths:
                print(f"     - {path}")
    
    return total_contracts, found_contracts, missing_contracts


def validate_config_consistency(config: dict) -> List[str]:
    """Проверка согласованности конфигурации."""
    print("\n🔍 Проверка согласованности конфигурации...")
    
    issues = []
    
    # Проверяем, что все компоненты имеют необходимые поля
    for comp_type in ['services', 'skills', 'tools']:
        components = config.get(comp_type, {})
        for comp_name, comp_config in components.items():
            if not isinstance(comp_config, dict):
                issues.append(f"Компонент {comp_type}.{comp_name} имеет некорректный формат конфигурации")
                continue
            
            # Проверяем, что у компонента есть хотя бы минимальная конфигурация
            if 'enabled' not in comp_config:
                print(f"  ⚠️  {comp_type}.{comp_name}: отсутствует поле 'enabled'")
    
    if not issues:
        print("  ✅ Конфигурация согласована")
    
    return issues


def main():
    """Основная функция проверки ресурсов."""
    print("🔧 Скрипт проверки ресурсов системы")
    print("=" * 50)
    
    # Определяем пути
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    config_dir = project_root / "core" / "config" / "defaults"
    
    # Загружаем основную конфигурацию
    dev_config_path = project_root / "dev.yaml.improved"  # Используем улучшенный файл
    registry_config_path = project_root / "registry.yaml"
    
    # Попробуем найти подходящий файл конфигурации
    config_path = None
    if dev_config_path.exists():
        config_path = dev_config_path
    elif (project_root / "dev.yaml").exists():
        config_path = project_root / "dev.yaml"
    elif registry_config_path.exists():
        config_path = registry_config_path
    
    if not config_path:
        print(f"❌ Не найден файл конфигурации")
        return 1
    
    print(f"📁 Используется конфигурация: {config_path}")
    config = load_yaml_file(config_path)
    
    if not config:
        print(f"❌ Не удалось загрузить конфигурацию из {config_path}")
        return 1
    
    # Проверяем директорию данных
    if not data_dir.exists():
        print(f"❌ Директория данных не найдена: {data_dir}")
        return 1
    
    print(f"📁 Директория данных: {data_dir}")
    
    # Выполняем проверки
    total_prompts, found_prompts, missing_prompts = validate_prompts(config, data_dir)
    total_contracts, found_contracts, missing_contracts = validate_contracts(config, data_dir)
    config_issues = validate_config_consistency(config)
    
    # Выводим сводку
    print("\n" + "=" * 50)
    print("📊 СВОДКА ПРОВЕРКИ РЕСУРСОВ")
    print("=" * 50)
    
    print(f"Промты: {found_prompts}/{total_prompts} найдено")
    print(f"Контракты: {found_contracts}/{total_contracts} найдено")
    
    total_resources = total_prompts + total_contracts
    found_resources = found_prompts + found_contracts
    missing_resources = len(missing_prompts) + len(missing_contracts)
    
    print(f"Всего ресурсов: {found_resources}/{total_resources} найдено")
    
    if missing_prompts:
        print(f"\n❌ Отсутствующие промты ({len(missing_prompts)}):")
        for capability, version in missing_prompts:
            print(f"  - {capability}@{version}")
    
    if missing_contracts:
        print(f"\n❌ Отсутствующие контракты ({len(missing_contracts)}):")
        for capability, version, direction in missing_contracts:
            print(f"  - {capability}@{version} ({direction})")
    
    if config_issues:
        print(f"\n⚠️  Проблемы с конфигурацией ({len(config_issues)}):")
        for issue in config_issues:
            print(f"  - {issue}")
    
    # Определяем статус
    if missing_resources == 0 and not config_issues:
        print(f"\n🎉 ВСЕ РЕСУРСЫ НАЙДЕНЫ И КОНФИГУРАЦИЯ КОРРЕКТНА!")
        return 0
    else:
        print(f"\n⚠️  НАЙДЕНЫ ПРОБЛЕМЫ С РЕСУРСАМИ!")
        print(f"   Отсутствующие ресурсы: {missing_resources}")
        print(f"   Проблемы с конфигурацией: {len(config_issues)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)