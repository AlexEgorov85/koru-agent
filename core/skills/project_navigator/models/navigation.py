"""
Модели данных для результатов навигации.
ОСОБЕННОСТИ:
- Простые структуры без избыточных полей
- Поддержка сериализации в JSON
- Четкое соответствие бизнес-логике навигации
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class NavigationResult(BaseModel):
    """
    Результат навигации к элементу кода.
    Пример использования:
    ```python
    result = NavigationResult(
        success=True,
        target_type="class",
        identifier="ProjectMapSkill",
        file_path="core/skills/project_map/skill.py",
        source_code="class ProjectMapSkill(BaseSkill):...",
        location={"start_line": 45, "end_line": 210}
    )
    ```
    """
    success: bool = Field(..., description="Успешность навигации")
    target_type: str = Field(..., description="Тип найденного элемента")
    identifier: str = Field(..., description="Имя или путь элемента")
    file_path: str = Field(..., description="Путь к файлу с элементом (относительный от корня проекта)")
    source_code: Optional[str] = Field(
        None,
        description="Исходный код элемента (при detail_level=FULL)"
    )
    signature: Optional[str] = Field(
        None,
        description="Сигнатура элемента (при detail_level=SIGNATURE)"
    )
    location: Optional[Dict[str, int]] = Field(
        None,
        description="Позиция в файле: {start_line, end_line, start_column, end_column}"
    )
    dependencies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Зависимости элемента: [{target_file, type}]"
    )
    error: Optional[str] = Field(
        None,
        description="Описание ошибки при неудачной навигации"
    )
    
    class Config:
        arbitrary_types_allowed = True