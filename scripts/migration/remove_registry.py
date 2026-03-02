"""
Скрипт удаления registry.yaml после успешной миграции на авто-обнаружение.

ИСПОЛЬЗОВАНИЕ:
    python scripts/migration/remove_registry.py [--force]

ЧТО ДЕЛАЕТ:
1. Создаёт бэкап registry.yaml
2. Проверяет что ResourceDiscovery работает корректно
3. Переименовывает registry.yaml в registry.yaml.deprecated
4. Выводит отчёт о миграции

ОПЦИИ:
    --force: Принудительное удаление без проверки
"""
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.infrastructure.discovery.resource_discovery import ResourceDiscovery


def create_backup(registry_path: str) -> Path:
    """Создание бэкапа registry.yaml"""
    registry_file = Path(registry_path)
    if not registry_file.exists():
        print(f"[WARN] Registry file not found: {registry_path}")
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = registry_file.parent / f"registry_{timestamp}.yaml.backup"
    
    shutil.copy2(registry_file, backup_path)
    print(f"[BACKUP] Created: {backup_path}")
    return backup_path


def validate_discovery(data_dir: str, profile: str) -> bool:
    """
    Валидация работы ResourceDiscovery.
    
    ВОЗВРАЩАЕТ:
    - bool: True если валидация успешна
    """
    print("[VALIDATE] Testing ResourceDiscovery...")
    
    discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)
    
    # Загружаем ресурсы
    prompts = discovery.discover_prompts()
    contracts = discovery.discover_contracts()
    manifests = discovery.discover_manifests()
    
    print(f"  - Prompts: {len(prompts)}")
    print(f"  - Contracts: {len(contracts)}")
    print(f"  - Manifests: {len(manifests)}")
    
    # Проверка что ресурсы загружены
    if len(prompts) == 0:
        print("[ERROR] No prompts loaded!")
        return False
    
    if len(manifests) == 0:
        print("[ERROR] No manifests loaded!")
        return False
    
    # Проверка что active ресурсы загружены в prod профиле
    if profile == 'prod':
        from core.models.data.prompt import PromptStatus
        non_active = [p for p in prompts if p.status != PromptStatus.ACTIVE]
        if non_active:
            print(f"[ERROR] Found non-active prompts in prod profile: {len(non_active)}")
            return False
    
    print("[VALIDATE] ResourceDiscovery working correctly")
    return True


def remove_registry(
    registry_path: str = 'registry.yaml',
    data_dir: str = 'data',
    profile: str = 'prod',
    force: bool = False
) -> bool:
    """
    Удаление registry.yaml.
    
    ПАРАМЕТРЫ:
    - registry_path: Путь к registry.yaml
    - data_dir: Директория данных
    - profile: Профиль для валидации
    - force: Принудительное удаление без проверки
    
    ВОЗВРАЩАЕТ:
    - bool: True если удаление успешно
    """
    print("=" * 60)
    print("REMOVE REGISTRY.YAML")
    print("=" * 60)
    print(f"Registry: {registry_path}")
    print(f"Data dir: {data_dir}")
    print(f"Profile: {profile}")
    print(f"Force: {force}")
    print()
    
    registry_file = Path(registry_path)
    
    # Проверка существования файла
    if not registry_file.exists():
        print(f"[WARN] Registry file not found: {registry_path}")
        return True
    
    # Валидация (если не force)
    if not force:
        print("[STEP 1/3] Validating ResourceDiscovery...")
        if not validate_discovery(data_dir, profile):
            print("\n[FAIL] Validation failed. Aborting removal.")
            return False
        print()
    
    # Создание бэкапа
    print("[STEP 2/3] Creating backup...")
    backup_path = create_backup(registry_path)
    if not backup_path:
        print("[FAIL] Backup creation failed")
        return False
    print()
    
    # Переименование файла
    print("[STEP 3/3] Renaming registry.yaml to registry.yaml.deprecated...")
    deprecated_path = registry_file.with_suffix('.yaml.deprecated')
    
    try:
        # Если deprecated файл уже существует, удаляем его
        if deprecated_path.exists():
            print(f"  Removing existing deprecated file: {deprecated_path}")
            deprecated_path.unlink()
        
        # Переименование
        shutil.move(str(registry_file), str(deprecated_path))
        print(f"  Renamed: {registry_file} -> {deprecated_path}")
    except Exception as e:
        print(f"[ERROR] Failed to rename: {e}")
        return False
    
    print()
    print("=" * 60)
    print("[SUCCESS] registry.yaml removed successfully!")
    print("=" * 60)
    print(f"\nBackup: {backup_path}")
    print(f"Deprecated: {deprecated_path}")
    print("\nTo restore registry.yaml, run:")
    print(f"  cp {deprecated_path} {registry_path}")
    print()
    
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Удаление registry.yaml после миграции на авто-обнаружение'
    )
    parser.add_argument(
        '--registry',
        default='registry.yaml',
        help='Путь к registry.yaml'
    )
    parser.add_argument(
        '--data-dir',
        default='data',
        help='Директория данных'
    )
    parser.add_argument(
        '--profile',
        default='prod',
        choices=['prod', 'sandbox', 'dev'],
        help='Профиль для валидации'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Принудительное удаление без проверки'
    )
    
    args = parser.parse_args()
    
    success = remove_registry(
        registry_path=args.registry,
        data_dir=args.data_dir,
        profile=args.profile,
        force=args.force
    )
    
    sys.exit(0 if success else 1)
