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

from core.models.data.prompt import Prompt
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource


class VersionPromoter:
    """
    Продвижение версий промптов.

    USAGE:
    ```python
    promoter = VersionPromoter(data_source, prompts_dir)
    
    await promoter.promote(
        prompt=improved_prompt,
        reason="A/B test winner",
        metrics={'success_rate': 0.95}
    )
    ```
    """

    def __init__(
        self,
        data_source: FileSystemDataSource,
        prompts_dir: Path
    ):
        """
        Инициализация.

        ARGS:
        - data_source: источник данных для сохранения
        - prompts_dir: директория для промптов
        """
        self.data_source = data_source
        self.prompts_dir = prompts_dir

    async def promote(
        self,
        prompt: Prompt,
        reason: str,
        metrics: Optional[Dict[str, float]] = None,
        ab_test_result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Продвижение новой версии.

        ARGS:
        - prompt: новая версия промпта
        - reason: причина продвижения
        - metrics: метрики новой версии
        - ab_test_result: результаты A/B теста

        RETURNS:
        - bool: успешно ли
        """
        try:
            # Обновление metadata
            prompt.metadata.update({
                'promoted_at': datetime.now().isoformat(),
                'promotion_reason': reason,
                'metrics': metrics or {},
                'ab_test_result': ab_test_result or {}
            })

            # Создание директории
            capability_dir = self.prompts_dir / prompt.capability.replace('.', '/')
            capability_dir.mkdir(parents=True, exist_ok=True)

            # Сохранение через data_source
            await self.data_source.save_prompt(
                capability_name=prompt.capability,
                version=prompt.version,
                prompt=prompt
            )

            # Сохранение в файл для наглядности
            prompt_file = capability_dir / f"{prompt.capability}.system_{prompt.version}.yaml"
            self._save_to_yaml(prompt, prompt_file)

            return True

        except Exception as e:
            pass  # Silently ignore promotion errors
            return False

    def _save_to_yaml(self, prompt: Prompt, file_path: Path) -> None:
        """
        Сохранение промпта в YAML файл.

        ARGS:
        - prompt: промпт
        - file_path: путь к файлу
        """
        yaml_content = f"""capability: {prompt.capability}
component_type: {prompt.component_type.value}
version: {prompt.version}
status: {prompt.status}
description: Автоматически улучшенная версия — {prompt.metadata.get('promotion_reason', 'N/A')}
content: |
{self._indent_content(prompt.content)}

variables: {prompt.variables or []}
metadata:
  promoted_at: {prompt.metadata.get('promoted_at', 'N/A')}
  promotion_reason: {prompt.metadata.get('promotion_reason', 'N/A')}
  metrics: {json.dumps(prompt.metadata.get('metrics', {}), indent=4)}
"""

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

    def _indent_content(self, content: str, indent: int = 2) -> str:
        """Добавление отступа к контенту"""
        lines = content.split('\n')
        return '\n'.join('  ' * indent + line for line in lines)

    async def rollback(
        self,
        capability: str,
        to_version: str
    ) -> bool:
        """
        Откат к предыдущей версии.

        ARGS:
        - capability: название способности
        - to_version: версия для отката

        RETURNS:
        - bool: успешно ли
        """
        try:
            # Загрузка версии
            prompt = await self.data_source.load_prompt(capability, to_version)

            if not prompt:
                return False

            # Обновление статуса
            prompt.status = 'active'
            prompt.metadata['rolled_back_at'] = datetime.now().isoformat()

            # Сохранение
            await self.data_source.save_prompt(
                capability_name=capability,
                version=to_version,
                prompt=prompt
            )

            return True

        except Exception as e:
            return False
