"""
Скрипт для управления миграциями промптов и контрактов.
"""
import argparse
import sys
import os
import json
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.infrastructure.migrations.manager import MigrationManager


def load_data(file_path: str) -> dict:
    """Загрузка данных из JSON файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(file_path: str, data: dict):
    """Сохранение данных в JSON файл."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def migrate(args):
    """Выполнение миграции."""
    manager = MigrationManager()
    
    # Загружаем данные
    data = load_data(args.file)
    
    # Применяем миграции
    migrated_data = manager.apply_migrations(
        migration_type=args.type,
        data=data,
        from_version=args.from_version,
        to_version=args.to_version
    )
    
    # Сохраняем мигрированные данные
    save_data(args.file, migrated_data)
    
    print(f"Миграция {args.type} из версии {args.from_version} в {args.to_version} выполнена успешно!")


def rollback(args):
    """Откат миграции."""
    manager = MigrationManager()
    
    # Загружаем данные
    data = load_data(args.file)
    
    # Откатываем миграции
    rolled_back_data = manager.rollback_migrations(
        migration_type=args.type,
        data=data,
        from_version=args.from_version,
        to_version=args.to_version
    )
    
    # Сохраняем данные после отката
    save_data(args.file, rolled_back_data)
    
    print(f"Откат миграции {args.type} из версии {args.to_version} в {args.from_version} выполнен успешно!")


def main():
    parser = argparse.ArgumentParser(description="Управление миграциями промптов и контрактов")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")
    
    # Команда миграции
    migrate_parser = subparsers.add_parser("migrate", help="Выполнить миграцию")
    migrate_parser.add_argument("--type", required=True, choices=["prompt", "contract"], help="Тип миграции")
    migrate_parser.add_argument("--file", required=True, help="Файл для миграции")
    migrate_parser.add_argument("--from-version", required=True, help="Исходная версия")
    migrate_parser.add_argument("--to-version", required=True, help="Целевая версия")
    migrate_parser.set_defaults(func=migrate)
    
    # Команда отката
    rollback_parser = subparsers.add_parser("rollback", help="Откатить миграцию")
    rollback_parser.add_argument("--type", required=True, choices=["prompt", "contract"], help="Тип миграции")
    rollback_parser.add_argument("--file", required=True, help="Файл для отката")
    rollback_parser.add_argument("--from-version", required=True, help="Исходная версия")
    rollback_parser.add_argument("--to-version", required=True, help="Целевая версия")
    rollback_parser.set_defaults(func=rollback)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()