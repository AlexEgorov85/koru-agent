

# Схемы для capability
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzeProjectInput(BaseModel):
    """Параметры для анализа проекта.
    
    Параметры capability `project_map.analyze_project`.
    
    Поля:
    - root_dir: корневая директория для анализа (по умолчанию ".")
    - max_depth: максимальная глубина анализа директорий (1-10)
    - include_tests: включать ли тестовые файлы
    - file_extensions: расширения файлов для анализа (по умолчанию [".py"])
    - include_code_units: включать ли детальную информацию о единицах кода
    
    Пример:
    ```python
    input_data = AnalyzeProjectInput(
        root_dir=".",
        max_depth=3,
        include_tests=False,
        file_extensions=[".py"],
        include_code_units=False
    )
    ```
    """
    
    root_dir: str = Field(".", description="Корневая директория для анализа")
    max_depth: int = Field(3, ge=1, le=10, description="Максимальная глубина анализа")
    include_tests: bool = Field(True, description="Включать тестовые файлы")
    file_extensions: List[str] = Field(["py"], description="Расширения файлов для анализа")
    include_code_units: bool = Field(False, description="Включать детальную информацию о единицах кода")

class AnalyzeProjectOutput(BaseModel):
    """Результат анализа проекта.
    
    Возвращается capability `project_map.analyze_project`.
    
    Поля:
    - success: успешность выполнения
    - project_structure: структура проекта в формате словаря
    - file_count: количество проанализированных файлов
    - code_unit_count: общее количество найденных единиц кода
    - error: описание ошибки (если есть)
    
    Пример:
    ```python
    output_data = AnalyzeProjectOutput(
        success=True,
        project_structure={...},
        file_count=42,
        code_unit_count=150,
        error=None
    )
    ```
    """
    
    success: bool
    project_structure: Dict[str, Any]
    file_count: int
    code_unit_count: int
    error: Optional[str] = None

class GetFileCodeUnitsInput(BaseModel):
    """Параметры для получения единиц кода из файла.
    
    Параметры capability `project_map.get_file_code_units`.
    
    Поля:
    - file_path: путь к файлу для анализа
    - include_source_code: включать ли исходный код в результат
    
    Пример:
    ```python
    input_data = GetFileCodeUnitsInput(
        file_path="core/skills/project_map/skill.py",
        include_source_code=False
    )
    ```
    """
    
    file_path: str = Field(..., description="Путь к файлу для анализа")
    include_source_code: bool = Field(False, description="Включать исходный код в результат")

class GetFileCodeUnitsOutput(BaseModel):
    """Результат получения единиц кода из файла.
    
    Возвращается capability `project_map.get_file_code_units`.
    
    Поля:
    - success: успешность выполнения
    - file_path: путь к проанализированному файлу
    - code_units: список единиц кода в формате словарей
    - unit_count: количество найденных единиц кода
    - error: описание ошибки (если есть)
    
    Пример:
    ```python
    output_data = GetFileCodeUnitsOutput(
        success=True,
        file_path="core/skills/project_map/skill.py",
        code_units=[{...}, {...}],
        unit_count=5,
        error=None
    )
    ```
    """
    
    success: bool
    file_path: str
    code_units: List[Dict[str, Any]]
    unit_count: int
    error: Optional[str] = None