"""
Классы для миграций промптов.
"""
from typing import Dict, Any
from core.infrastructure.migrations.base import PromptMigration


class AddTagsFieldMigration(PromptMigration):
    """
    Миграция для добавления поля tags к промптам.
    """
    version_from = "1.0.0"
    version_to = "1.1.0"

    def up(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        if "metadata" not in prompt_data:
            prompt_data["metadata"] = {}
        if "tags" not in prompt_data["metadata"]:
            prompt_data["metadata"]["tags"] = []
        return prompt_data

    def down(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        if "metadata" in prompt_data and "tags" in prompt_data["metadata"]:
            del prompt_data["metadata"]["tags"]
            # Удаляем metadata, если оно стало пустым
            if not prompt_data["metadata"]:
                del prompt_data["metadata"]
        return prompt_data