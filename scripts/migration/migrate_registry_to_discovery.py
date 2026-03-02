"""
Скрипт миграции registry.yaml на авто-обнаружение через файловую систему.

ИСПОЛЬЗОВАНИЕ:
    python scripts/migration/migrate_registry_to_discovery.py

ЧТО ДЕЛАЕТ:
1. Загружает registry.yaml
2. Проверяет что все версии из registry существуют в файлах
3. Проверяет что статусы в файлах соответствуют declared в registry
4. Создаёт отчёт о миграции
"""
import yaml
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
from core.models.data.prompt import PromptStatus
from core.models.data.manifest import ComponentStatus


def load_registry(registry_path: str) -> dict:
    """Загрузка registry.yaml"""
    registry_file = Path(registry_path)
    if not registry_file.exists():
        print(f"❌ Файл реестра не найден: {registry_path}")
        return None
    
    with open(registry_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def find_prompt_file_in_discovery(discovery: ResourceDiscovery, capability: str, version: str) -> bool:
    """Проверка существует ли промпт в discovery"""
    return discovery.get_prompt(capability, version) is not None


def find_contract_file_in_discovery(discovery: ResourceDiscovery, capability: str, version: str, direction: str) -> bool:
    """Проверка существует ли контракт в discovery"""
    return discovery.get_contract(capability, version, direction) is not None


def migrate_registry(registry_path: str = 'registry.yaml', data_dir: str = 'data', profile: str = 'prod'):
    """
    Миграция registry.yaml на авто-обнаружение.
    
    ПАРАМЕТРЫ:
    - registry_path: Путь к registry.yaml
    - data_dir: Директория данных
    - profile: Профиль для проверки (prod/sandbox)
    """
    print("=" * 60)
    print("MIGRATION: registry.yaml TO AUTO-DISCOVERY")
    print("=" * 60)
    print(f"Registry: {registry_path}")
    print(f"Data dir: {data_dir}")
    print(f"Profile: {profile}")
    print()
    
    # 1. Загружаем registry
    print("[1/6] Loading registry.yaml...")
    registry = load_registry(registry_path)
    if not registry:
        return False
    
    # 2. Инициализируем ResourceDiscovery
    print("[2/6] Initializing ResourceDiscovery...")
    discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)
    
    # 3. Сканируем ресурсы
    print("[3/6] Scanning resources...")
    prompts = discovery.discover_prompts()
    contracts = discovery.discover_contracts()
    manifests = discovery.discover_manifests()
    
    print(f"   Found prompts: {len(prompts)}")
    print(f"   Found contracts: {len(contracts)}")
    print(f"   Found manifests: {len(manifests)}")
    print()
    
    # 4. Проверяем active_prompts из registry
    print("[4/6] Checking active_prompts...")
    active_prompts = registry.get('active_prompts', {})
    errors = []
    warnings = []
    
    for capability, version in active_prompts.items():
        if not find_prompt_file_in_discovery(discovery, capability, version):
            errors.append(f"  [ERROR] Prompt {capability}@{version} not found in FS")
        else:
            prompt = discovery.get_prompt(capability, version)
            if prompt.status != PromptStatus.ACTIVE:
                warnings.append(f"  [WARN] Prompt {capability}@{version} has status '{prompt.status.value}' instead of 'active'")
            else:
                print(f"  [OK] {capability}@{version}")
    
    # 5. Проверяем active_contracts из registry
    print("\n[5/6] Checking active_contracts...")
    active_contracts = registry.get('active_contracts', {})
    
    for capability, versions in active_contracts.items():
        if isinstance(versions, dict):
            # Проверяем input и output
            if 'input' in versions:
                input_ver = versions['input']
                if not find_contract_file_in_discovery(discovery, capability, input_ver, 'input'):
                    errors.append(f"  [ERROR] Input contract {capability}@{input_ver} not found in FS")
                else:
                    print(f"  [OK] {capability}@{input_ver} (input)")
            
            if 'output' in versions:
                output_ver = versions['output']
                if not find_contract_file_in_discovery(discovery, capability, output_ver, 'output'):
                    errors.append(f"  [ERROR] Output contract {capability}@{output_ver} not found in FS")
                else:
                    print(f"  [OK] {capability}@{output_ver} (output)")
        else:
            # Старый формат без разделения на input/output
            if not find_contract_file_in_discovery(discovery, capability, versions, 'input'):
                errors.append(f"  [ERROR] Contract {capability}@{versions} not found in FS")
            else:
                print(f"  [OK] {capability}@{versions}")
    
    # 6. Проверяем манифесты
    print("\n[6/6] Checking manifests...")
    
    # Services
    services = registry.get('services', {})
    for service_name, service_info in services.items():
        if isinstance(service_info, dict) and service_info.get('enabled', False):
            manifest = discovery.get_manifest('service', service_name)
            if manifest:
                print(f"  [OK] Service manifest: {service_name}")
            else:
                warnings.append(f"  [WARN] Service manifest {service_name} not found")
    
    # Skills
    skills = registry.get('skills', {})
    for skill_name, skill_info in skills.items():
        if isinstance(skill_info, dict) and skill_info.get('enabled', False):
            manifest = discovery.get_manifest('skill', skill_name)
            if manifest:
                print(f"  [OK] Skill manifest: {skill_name}")
            else:
                warnings.append(f"  [WARN] Skill manifest {skill_name} not found")
    
    # Tools
    tools = registry.get('tools', {})
    for tool_name, tool_info in tools.items():
        if isinstance(tool_info, dict) and tool_info.get('enabled', False):
            manifest = discovery.get_manifest('tool', tool_name)
            if manifest:
                print(f"  [OK] Tool manifest: {tool_name}")
            else:
                warnings.append(f"  [WARN] Tool manifest {tool_name} not found")
    
    # 7. Вывод результатов
    print("\n" + "=" * 60)
    print("MIGRATION RESULTS")
    print("=" * 60)
    
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for error in errors:
            print(error)
    
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(warning)
    
    if not errors and not warnings:
        print("\n[SUCCESS] ALL CHECKS PASSED!")
        print("\nregistry.yaml can be safely removed.")
        print("Resources are fully discoverable via file system.")
        return True
    elif not errors:
        print("\n[OK] NO CRITICAL ERRORS")
        print("\nregistry.yaml can be removed after fixing warnings.")
        return True
    else:
        print("\n[FAIL] CRITICAL ERRORS FOUND")
        print("\nDO NOT REMOVE registry.yaml until errors are fixed.")
        return False


def create_backup(registry_path: str) -> bool:
    """Создание бэкапа registry.yaml"""
    import shutil
    
    registry_file = Path(registry_path)
    if not registry_file.exists():
        return False
    
    backup_path = registry_file.with_suffix('.yaml.backup')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = registry_file.parent / f"registry_{timestamp}.yaml.backup"
    
    shutil.copy2(registry_file, backup_path)
    print(f"[BACKUP] Created: {backup_path}")
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Миграция registry.yaml на авто-обнаружение')
    parser.add_argument('--registry', default='registry.yaml', help='Путь к registry.yaml')
    parser.add_argument('--data-dir', default='data', help='Директория данных')
    parser.add_argument('--profile', default='prod', choices=['prod', 'sandbox', 'dev'], help='Профиль проверки')
    parser.add_argument('--backup', action='store_true', help='Создать бэкап registry.yaml')
    
    args = parser.parse_args()
    
    # Создание бэкапа если запрошено
    if args.backup:
        create_backup(args.registry)
    
    # Запуск миграции
    success = migrate_registry(
        registry_path=args.registry,
        data_dir=args.data_dir,
        profile=args.profile
    )
    
    # Вывод статистики
    print("\n" + "=" * 60)
    print("ResourceDiscovery Statistics:")
    print("=" * 60)
    
    # Создаём discovery ещё раз для статистики
    discovery = ResourceDiscovery(base_dir=Path(args.data_dir), profile=args.profile)
    discovery.discover_prompts()
    discovery.discover_contracts()
    discovery.discover_manifests()
    
    print(discovery.get_validation_report())
    
    sys.exit(0 if success else 1)
