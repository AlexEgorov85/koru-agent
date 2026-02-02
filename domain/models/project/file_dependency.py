"""Модели для представления зависимостей между файлами проекта.

Этот модуль содержит модель для работы с зависимостями между файлами:
- FileDependency - зависимость между файлами

Модель разработана для:
1. Отслеживания зависимостей между файлами
2. Анализа архитектуры проекта
3. Определения порядка загрузки файлов
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FileDependency:
    """Зависимость между файлами.
    Представляет отношения зависимости между файлами проекта.

    Атрибуты:
    - source_file: файл-источник зависимости
    - target_file: файл-цель зависимости
    - dependency_type: тип зависимости ("import", "inheritance", "function_call")

    Пример:
    ```python
    dependency = FileDependency(
        source_file="core/skills/project_map/skill.py",
        target_file="core/skills/base_skill.py",
        dependency_type="import"
    )
    ```
    """

    source_file: str
    target_file: str
    dependency_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'source_file': self.source_file,
            'target_file': self.target_file,
            'dependency_type': self.dependency_type
        }