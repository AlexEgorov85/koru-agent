"""ProjectMapSkill - навык для анализа структуры проекта.

Предоставляет возможность создания детальной карты проекта с анализом:
- Файловой структуры
- Зависимостей между файлами
- Единиц кода (классы, функции, переменные)
- Точек входа в приложение

Навык интегрируется с существующими инструментами:
- FileListerTool: для получения списка файлов
- FileReaderTool: для чтения содержимого файлов
- ASTParserTool: для анализа структуры кода

Примеры использования:

1. Анализ всего проекта:
```python
result = await project_map_skill.execute_capability(
    capability="project_map.analyze_project",
    parameters={
        "root_dir": ".",
        "max_depth": 3,
        "include_tests": False,
        "file_extensions": [".py"],
        "include_code_units": True
    },
    context=session_context
)
```

2. Анализ конкретного файла:
```python
result = await project_map_skill.execute_capability(
    capability="project_map.get_file_code_units",
    parameters={
        "file_path": "core/skills/project_map/skill.py",
        "include_source_code": False
    },
    context=session_context
)
```

3. Получение структуры проекта для LLM:
```python
project_structure = result.result["project_structure"]
print(f"Проект содержит {project_structure['total_files']} файлов")
```

Интеграция с другими навыками:
- PlanningSkill может использовать карту проекта для планирования задач
- CodeDefinitionSkill может использовать CodeUnit для поиска определений
- CodeSearchSkill может использовать структуру для семантического поиска

Компоненты навыка:
- models: модели данных для представления кода и структуры проекта
- components: компоненты для обработки AST и построения структуры
- skill: основной класс навыка с capability
"""

from .skill import ProjectMapSkill

__all__ = ['ProjectMapSkill']
