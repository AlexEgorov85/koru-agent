"""Модели данных для ProjectMapSkill.

Содержит основные модели для представления:
- CodeUnit - единиц кода (классы, функции, переменные)
- ProjectStructure - карты проекта
- Вспомогательные структуры для хранения метаданных

Модели следуют принципам:
1. Иммутабельность для потокобезопасности
2. Четкая типизация через Pydantic
3. Легкая сериализация в JSON
4. Расширяемость через метаданные

Пример использования:
```python
from core.skills.project_map.models.code_unit import CodeUnit, CodeUnitType
from core.skills.project_map.models.project_map import ProjectStructure

# Создание CodeUnit
unit = CodeUnit(
    id="func_main_123",
    name="main",
    type=CodeUnitType.FUNCTION,
    location=Location(
        file_path="core/main.py",
        start_line=10,
        end_line=15,
        start_column=1,
        end_column=20
    ),
    code_span=CodeSpan(source_code="def main():\n    print('Hello')")
)

# Создание ProjectStructure
project = ProjectStructure(root_dir=".")
"""

from .code_unit import CodeUnit, CodeUnitType, Location, CodeSpan
from .project_map import (
ProjectStructure, FileInfo, DirectoryInfo,
EntryPointInfo, FileDependency
)

all = [
'CodeUnit',
'CodeUnitType',
'Location',
'CodeSpan',
'ProjectStructure',
'FileInfo',
'DirectoryInfo',
'EntryPointInfo',
'FileDependency'
]