"""
Компоненты ProjectMapSkill.

Содержит отдельные компоненты для работы с различными аспектами анализа проекта:
- ASTProcessor: обработка AST деревьев
- CodeUnitBuilder: построение CodeUnit из AST узлов
- DependencyAnalyzer: анализ зависимостей между файлами
- ProjectStructureBuilder: построение иерархической структуры проекта

Компоненты следуют принципам:
1. Единственная ответственность (SOLID)
2. Взаимозаменяемость
3. Тестируемость
4. Минимальные зависимости от внешних ресурсов

Примеры использования:

1. Обработка AST:
```python
ast_processor = ASTProcessor(project_map_skill)
code_units = ast_processor.process_file_ast(tree, "core/main.py", source_code)
```

2. Построение структуры проекта:
```python
structure_builder = ProjectStructureBuilder(project_map_skill)
project_structure = structure_builder.build_project_structure(
    root_dir=".",
    files_info=file_list,
    code_units_by_file=code_units_by_file
)
```

3. Анализ зависимостей:
```python
dependency_analyzer = DependencyAnalyzer(project_map_skill)
dependencies = dependency_analyzer.analyze_file_dependencies(
    file_path="core/main.py",
    code_units=code_units
)
```

Каждый компонент работает с конкретным аспектом анализа, что позволяет легко расширять и модифицировать логику.
"""

from .ast_processor import ASTProcessor
from .code_unit_builder import CodeUnitBuilder
from .dependency_analyzer import DependencyAnalyzer
from .project_structure_builder import ProjectStructureBuilder

__all__ = [
    'ASTProcessor',
    'CodeUnitBuilder',
    'DependencyAnalyzer',
    'ProjectStructureBuilder'
]
