"""
VersionPromoter — продвижение лучших версий промптов.

ОТВЕТСТВЕННОСТЬ:
- Сохранение новой версии промпта
- Обновление metadata
- Логирование изменений
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from core.models.data.prompt import Prompt
from core.infrastructure.loading.resource_loader import ResourceLoader


class VersionPromoter:
    """
    Продвижение версий промптов.

    USAGE:
    ```python
    promoter = VersionPromoter(prompts_dir)

    await promoter.promote(
        prompt=improved_prompt,
        reason="A/B test winner",
        metrics={'success_rate': 0.95}
    )
    ```
    """

    def __init__(
        self,
        prompts_dir: Path
    ):
        """
        Инициализация.

        ARGS:
        - prompts_dir: Директория с промптами
        """
        self.prompts_dir = Path(prompts_dir)

    def save_prompt(self, prompt: Prompt) -> Path:
        """
        Сохранить промпт в YAML файл.

        ARGS:
        - prompt: Объект промпта для сохранения

        RETURNS:
        - Path: Путь к сохранённому файлу
        """
        type_dir = prompt.component_type.value if hasattr(prompt, 'component_type') else 'skill'
        target_dir = self.prompts_dir / type_dir

        capability_parts = prompt.capability.split('.')
        for part in capability_parts[:-1]:
            target_dir /= part
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / f"{prompt.version}.yaml"

        data = {
            "capability": prompt.capability,
            "version": prompt.version,
            "status": prompt.status.value,
            "component_type": prompt.component_type.value if hasattr(prompt, 'component_type') else 'skill',
            "content": prompt.content,
            "variables": [v.model_dump() for v in prompt.variables],
            "metadata": prompt.metadata,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return file_path

    def promote(
        self,
        prompt: Prompt,
        reason: str,
        metrics: Optional[Dict[str, float]] = None,
        ab_test_result: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Продвижение новой версии — сохранение + логирование.

        ARGS:
        - prompt: новая версия промпта
        - reason: причина продвижения
        - metrics: метрики новой версии
        - ab_test_result: результаты A/B теста

        RETURNS:
        - Path: путь к сохранённому файлу
        """
        updated_metadata = dict(prompt.metadata)
        updated_metadata.update({
            'promoted_at': datetime.now().isoformat(),
            'promotion_reason': reason,
            'metrics': metrics or {},
            'ab_test_result': ab_test_result or {}
        })

        # Prompt frozen — создаём копию с обновлённым metadata
        updated_prompt = prompt.model_copy(update={'metadata': updated_metadata})
        return self.save_prompt(updated_prompt)
