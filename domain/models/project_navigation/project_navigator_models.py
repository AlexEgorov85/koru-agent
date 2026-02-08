"""
Схемы валидации для ProjectNavigatorSkill
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class NavigationInput(BaseModel):
    """Входные параметры для навигации по проекту"""
    query: str
    search_type: str  # "code_elements", "dependencies", "files", etc.
    filters: Optional[Dict[str, Any]] = {}
    max_results: Optional[int] = 50
    include_context: Optional[bool] = True


class NavigationOutput(BaseModel):
    """Выходные параметры для навигации по проекту"""
    success: bool
    results: List[Dict[str, Any]]
    result_count: int
    query_time: Optional[float]
    error: Optional[str]


class FindCodeElementsInput(BaseModel):
    """Входные параметры для поиска элементов кода"""
    element_name: str
    element_type: Optional[str] = None  # "class", "function", "variable", etc.
    file_path: Optional[str] = None
    search_scope: Optional[str] = "project"  # "file", "directory", "project"
    case_sensitive: Optional[bool] = False


class FindCodeElementsOutput(BaseModel):
    """Выходные параметры для поиска элементов кода"""
    success: bool
    elements: List[Dict[str, Any]]
    element_count: int
    error: Optional[str]


class FindDependenciesInput(BaseModel):
    """Входные параметры для поиска зависимостей"""
    target: str  # файл, класс или функция
    dependency_type: Optional[str] = "all"  # "imports", "calls", "inheritance", etc.
    direction: Optional[str] = "both"  # "incoming", "outgoing", "both"
    max_depth: Optional[int] = 3


class FindDependenciesOutput(BaseModel):
    """Выходные параметры для поиска зависимостей"""
    success: bool
    dependencies: List[Dict[str, Any]]
    dependency_count: int
    error: Optional[str]