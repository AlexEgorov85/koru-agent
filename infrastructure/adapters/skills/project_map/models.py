"""
Pydantic-схемы валидации для ProjectMapSkill
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AnalyzeProjectInput(BaseModel):
    """Входные параметры для анализа проекта"""
    directory: str
    max_items: Optional[int] = 100
    include_tests: Optional[bool] = False
    include_hidden: Optional[bool] = False
    file_extensions: Optional[List[str]] = [".py", ".js", ".ts", ".tsx", ".jsx"]
    include_code_units: Optional[bool] = True
    max_depth: Optional[int] = 5


class AnalyzeProjectOutput(BaseModel):
    """Выходные параметры для анализа проекта"""
    success: bool
    project_structure: Optional[Dict[str, Any]]
    file_count: Optional[int]
    code_unit_count: Optional[int]
    scan_duration: Optional[float]
    error: Optional[str]


class GetFileCodeUnitsInput(BaseModel):
    """Входные параметры для получения единиц кода из файла"""
    file_path: str
    include_details: Optional[bool] = True


class GetFileCodeUnitsOutput(BaseModel):
    """Выходные параметры для получения единиц кода из файла"""
    success: bool
    file_path: str
    code_units: List[Dict[str, Any]]
    unit_count: int
    error: Optional[str]