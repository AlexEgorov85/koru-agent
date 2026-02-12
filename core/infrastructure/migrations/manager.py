"""
Менеджер миграций для промптов и контрактов.
"""
import os
import logging
from typing import Dict, Any, List
from pathlib import Path

from core.infrastructure.migrations.base import Migration
from core.infrastructure.migrations.prompt import AddTagsFieldMigration
from core.infrastructure.migrations.contract import AddDescriptionFieldMigration


class MigrationManager:
    """
    Менеджер для управления миграциями промптов и контрактов.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.migrations = {
            "prompt": [
                AddTagsFieldMigration()
            ],
            "contract": [
                AddDescriptionFieldMigration()
            ]
        }

    def get_applicable_migrations(self, migration_type: str, from_version: str, to_version: str) -> List[Migration]:
        """
        Получение применимых миграций для указанного типа и диапазона версий.
        
        ARGS:
        - migration_type: тип миграции ('prompt' или 'contract')
        - from_version: начальная версия
        - to_version: конечная версия
        
        RETURNS:
        - список применимых миграций
        """
        applicable = []
        migrations = self.migrations.get(migration_type, [])
        
        for migration in migrations:
            # Простая проверка версий (в реальном приложении нужно использовать семвер)
            if migration.version_from == from_version and migration.version_to == to_version:
                applicable.append(migration)
                
        return applicable

    def apply_migrations(self, migration_type: str, data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """
        Применение миграций к данным.
        
        ARGS:
        - migration_type: тип миграции ('prompt' или 'contract')
        - data: данные для миграции
        - from_version: начальная версия
        - to_version: конечная версия
        
        RETURNS:
        - мигрированные данные
        """
        migrations = self.get_applicable_migrations(migration_type, from_version, to_version)
        
        migrated_data = data.copy()
        for migration in migrations:
            self.logger.info(f"Применение миграции {migration.version_from} → {migration.version_to}")
            migrated_data = migration.up(migrated_data)
            
        return migrated_data

    def rollback_migrations(self, migration_type: str, data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """
        Откат миграций для данных.
        
        ARGS:
        - migration_type: тип миграции ('prompt' или 'contract')
        - data: данные для отката
        - from_version: начальная версия
        - to_version: конечная версия
        
        RETURNS:
        - данные после отката
        """
        migrations = self.get_applicable_migrations(migration_type, from_version, to_version)
        
        rolled_back_data = data.copy()
        for migration in reversed(migrations):
            self.logger.info(f"Откат миграции {migration.version_to} → {migration.version_from}")
            rolled_back_data = migration.down(rolled_back_data)
            
        return rolled_back_data