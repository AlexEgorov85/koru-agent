"""
Модели данных для результатов поиска элементов кода.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """
    Один результат поиска элемента кода.
    Пример:
    ```python
    result = SearchResult(
        name="ProjectMapSkill",
        file_path="core/skills/project_map/skill.py",
        type="class",
        line=45,
        relevance_score=0.95,
        context="class ProjectMapSkill(BaseSkill):"
    )
    ```
    """
    name: str = Field(..., description="Имя элемента")
    file_path: str = Field(..., description="Путь к файлу (относительный от корня проекта)")
    type: str = Field(..., description="Тип элемента (class, function, method)")
    line: int = Field(..., description="Номер строки начала элемента", ge=1)
    relevance_score: float = Field(
        ...,
        description="Релевантность результата (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    context: str = Field(..., description="Контекстная информация об элементе")


class SearchResultSet(BaseModel):
    """
    Набор результатов поиска.
    Пример:
    ```python
    results = SearchResultSet(
        success=True,
        query="build",
        results=[search_result1, search_result2, ...],
        total_results=5
    )
    ```
    """
    success: bool = Field(..., description="Успешность поиска")
    query: str = Field(..., description="Исходный поисковый запрос")
    results: List[SearchResult] = Field(
        default_factory=list,
        description="Список найденных элементов",
        max_items=20
    )
    total_results: int = Field(0, description="Общее количество найденных элементов", ge=0)
    error: Optional[str] = Field(None, description="Описание ошибки при неудачном поиске")