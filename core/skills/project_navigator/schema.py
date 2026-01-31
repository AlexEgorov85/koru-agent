"""
Pydantic схемы для валидации входных параметров навыка навигации.
СООТВЕТСТВИЕ ПРИНЦИПАМ:
- Простые схемы без избыточной вложенности
- Четкие ограничения на значения
- Поддержка валидации через ExecutionGateway
- Совместимость с существующими сервисами
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class NavigationTargetType(str, Enum):
    """Типы целевых элементов для навигации."""
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"


class NavigationDetailLevel(str, Enum):
    """Уровни детализации результата навигации."""
    SIGNATURE = "signature"  # Только сигнатура
    BODY = "body"            # Тело без контекста
    FULL = "full"            # Полный код с контекстом


class NavigationInput(BaseModel):
    """
    Параметры для навигации к элементу кода.
    Пример использования:
    ```python
    params = NavigationInput(
        target_type=NavigationTargetType.CLASS,
        identifier="ProjectMapSkill",
        file_path="core/skills/project_map/skill.py",
        detail_level=NavigationDetailLevel.FULL
    )
    ```
    """
    target_type: NavigationTargetType = Field(
        ..., description="Тип целевого элемента"
    )
    identifier: str = Field(
        ..., description="Имя элемента или путь к файлу", min_length=1, max_length=255
    )
    file_path: Optional[str] = Field(
        None,
        description=(
            "Путь к файлу (обязателен для классов/функций/методов). "
            "Поддерживает абсолютные и относительные пути, "
            "автоматически нормализуется для поиска в структуре проекта."
        ),
        max_length=512
    )
    class_name: Optional[str] = Field(
        None,
        description="Имя класса (обязательно для методов)",
        max_length=128
    )
    detail_level: NavigationDetailLevel = Field(
        NavigationDetailLevel.FULL,
        description="Уровень детализации результата"
    )
    include_dependencies: bool = Field(
        False,
        description="Включать информацию о зависимостях"
    )
    dependency_depth: int = Field(
        1, ge=1, le=3,
        description="Глубина анализа зависимостей (1-3)"
    )
    
    @field_validator('dependency_depth')
    @classmethod
    def validate_dependency_depth(cls, v: int) -> int:
        """Ограничение глубины для защиты от экспоненциального роста."""
        return min(3, max(1, v))


class SearchInput(BaseModel):
    """
    Параметры для поиска элементов кода.
    Пример использования:
    ```python
    params = SearchInput(
        query="build",
        element_types=["class", "function", "method"],
        max_results=5
    )
    ```
    """
    query: str = Field(
        ..., description="Строка поиска", min_length=1, max_length=100
    )
    scope: str = Field(
        "global",
        description="Область поиска: 'global', 'file:<path>', 'module:<name>'"
    )
    element_types: List[str] = Field(
        ["class", "function", "method"],
        description="Типы элементов для поиска",
        min_items=1,
        max_items=5
    )
    exact_match: bool = Field(
        False,
        description="Точное совпадение имени"
    )
    max_results: int = Field(
        10, ge=1, le=20,
        description="Максимальное количество результатов"
    )
    
    @field_validator('max_results')
    @classmethod
    def validate_max_results(cls, v: int) -> int:
        """Ограничение количества результатов для производительности."""
        return min(20, max(1, v))


class FindUsagesInput(BaseModel):
    """
    Параметры для поиска мест использования символа.
    """
    symbol_name: str = Field(..., description="Имя символа для поиска", min_length=1)
    symbol_type: Optional[str] = Field(
        None,
        description="Тип символа (опционально): 'class', 'function', 'variable'"
    )
    file_path: Optional[str] = Field(
        None,
        description="Ограничение поиска конкретным файлом"
    )
    max_results: int = Field(20, ge=1, le=50, description="Максимальное количество результатов")


class GetInheritanceChainInput(BaseModel):
    """
    Параметры для получения цепочки наследования класса.
    """
    class_name: str = Field(..., description="Имя класса", min_length=1)
    file_path: str = Field(..., description="Путь к файлу с классом", min_length=1)
    max_depth: int = Field(5, ge=1, le=10, description="Максимальная глубина анализа")