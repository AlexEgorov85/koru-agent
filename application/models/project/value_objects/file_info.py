"""Модели для представления информации о файле проекта.

Этот модуль содержит модель для работы с информацией о файле проекта:
- FileInfo - информация о файле

Модель разработана для:
1. Представления метаданных файла
2. Связывания файла с единицами кода
3. Отслеживания зависимостей между файлами
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from domain.core.project.value_objects.code_unit import CodeUnit


@dataclass
class FileInfo:
    """Информация о файле в проекте.
    Содержит метаданные о файле и ссылки на связанные единицы кода.

    Атрибуты:
    - file_path: путь к файлу относительно корня проекта
    - size: размер файла в байтах
    - last_modified: время последнего изменения в timestamp
    - code_units: список объектов CodeUnit в файле
    - imports: список импортируемых модулей
    - exports: список экспортируемых символов
    - dependencies: список зависимостей от других файлов

    Пример:
    ```python
    file_info = FileInfo(
        file_path="core/skills/project_map/skill.py",
        size=15000,
        last_modified=1700000000,
        code_units=[code_unit1, code_unit2],
        imports=["core.skills.base_skill", "models.capability"],
        exports=["ProjectMapSkill"],
        dependencies=["core.skills.base_skill"]
    )
    ```
    """

    file_path: str
    size: int
    last_modified: float
    code_units: List[CodeUnit] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'file_path': self.file_path,
            'size': self.size,
            'last_modified': self.last_modified,
            'code_unit_count': len(self.code_units),
            'imports_count': len(self.imports),
            'exports_count': len(self.exports),
            'dependencies_count': len(self.dependencies)
        }