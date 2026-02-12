"""
Классы для миграций контрактов.
"""
from typing import Dict, Any
from core.infrastructure.migrations.base import ContractMigration


class AddDescriptionFieldMigration(ContractMigration):
    """
    Миграция для добавления поля description к контрактам.
    """
    version_from = "1.0.0"
    version_to = "1.1.0"

    def up(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        if "description" not in contract_data:
            contract_data["description"] = "Default description"
        return contract_data

    def down(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        if "description" in contract_data:
            del contract_data["description"]
        return contract_data