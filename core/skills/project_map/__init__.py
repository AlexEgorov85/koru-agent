"""
ProjectMapSkill - навык для анализа структуры проекта через сервисы анализа кода.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Полный отказ от собственных компонентов анализа (ASTProcessor, CodeUnitBuilder)
2. Использование сервисов ASTProcessingService и CodeNavigationService
3. Бизнес-логика построения структуры проекта остаётся в навыке
4. Семантический анализ выполняется навыком (не сервисами)

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Сервисы предоставляют ТОЛЬКО детерминированные данные (структура, символы)
- Навык принимает решения на основе данных + при необходимости вызывает LLM
- Чёткое разделение: инфраструктура (сервисы) vs бизнес-логика (навык)

Примеры использования:
1. Анализ всего проекта:
    ```python
    result = await project_map_skill.execute(
        capability=system_context.get_capability("project_map.analyze_project"),
        parameters={"root_dir": ".", "max_depth": 3, "include_tests": False},
        context=session_context
    )
    project_structure = result.result  # Объект ProjectStructure
    ```

2. Анализ конкретного файла:
    ```python
    result = await project_map_skill.execute(
        capability=system_context.get_capability("project_map.get_file_code_units"),
        parameters={"file_path": "core/skills/project_map/skill.py"},
        context=session_context
    )
    ```
"""
from .skill import ProjectMapSkill

__all__ = ['ProjectMapSkill']