"""Модели для представления информации о директории проекта.

Этот модуль содержит модель для работы с информацией о директории проекта:
- DirectoryInfo - информация о директории

Модель разработана для:
1. Представления иерархии директорий
2. Отслеживания файлов в директориях
3. Подсчета метрик директорий
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class DirectoryInfo:
    """Информация о директории в проекте.
    Содержит иерархическую информацию о директории и ее содержимом.

    Атрибуты:
    - path: путь к директории относительно корня проекта
    - name: имя директории
    - files: список файлов в директории (только имена)
    - subdirectories: список поддиректорий (только пути)
    - total_files: общее количество файлов в директории и поддиректориях
    - total_size: общий размер файлов в байтах

    Пример:
    ```python
    dir_info = DirectoryInfo(
        path="core/skills",
        name="skills",
        files=["__init__.py", "base_skill.py"],
        subdirectories=["core/skills/planning", "core/skills/project_map"],
        total_files=15,
        total_size=50000
    )
    ```
    """

    path: str
    name: str
    files: List[str] = field(default_factory=list)
    subdirectories: List[str] = field(default_factory=list)
    total_files: int = 0
    total_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'path': self.path,
            'name': self.name,
            'file_count': len(self.files),
            'subdirectory_count': len(self.subdirectories),
            'total_files': self.total_files,
            'total_size': self.total_size
        }