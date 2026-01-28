"""
Pydantic схемы для валидации входных и выходных данных навыка.

ОСОБЕННОСТИ:
- Полная совместимость с FileListerInput через наследование
- Автоматическое преобразование высокоуровневых флагов (include_tests) в низкоуровневые паттерны
- Поддержка прямой передачи параметров инструментам без преобразований
- Сохранение удобства использования для конечного пользователя
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator, computed_field

from models.code_unit import CodeUnit


class AnalyzeProjectInput(BaseModel):
    """
    Параметры для анализа проекта с идеальной совместимостью с FileListerInput.
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Прямое наследование параметров от FileListerInput (path, max_items, file_extensions)
    2. Автоматическое преобразование высокоуровневых флагов в низкоуровневые паттерны:
       - include_tests → exclude_patterns (добавление 'test/**', 'tests/**')
       - include_hidden → exclude_patterns (удаление '.*' из исключений)
    3. Поддержка прямой передачи параметров инструментам без преобразований
    
    ПОЛЯ ИНСТРУМЕНТА (прямая совместимость):
        - path: корневая директория для анализа
        - max_items: максимальное количество файлов
        - file_extensions: фильтр по расширениям файлов
        - exclude_patterns: шаблоны для исключения (автоматически дополняются из флагов)
        - include_files: всегда True (анализируем только файлы)
        - include_directories: всегда True (директории анализируем)
    
    УДОБНЫЕ ФЛАГИ (высокоуровневые):
        - include_tests: включать ли тестовые файлы (преобразуется в exclude_patterns)
        - include_hidden: включать ли скрытые файлы/директории (преобразуется в exclude_patterns)
        - include_code_units: включать ли детальную информацию о единицах кода
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        # Простой вызов с высокоуровневыми флагами
        input = AnalyzeProjectInput(
            directory=".",
            include_tests=False,  # Автоматически добавит 'test/**', 'tests/**' в exclude_patterns
            include_hidden=False  # Автоматически добавит '.*' в exclude_patterns
        )
        
        # Продвинутый вызов с прямым контролем паттернов
        input = AnalyzeProjectInput(
            directory=".",
            exclude_patterns=["__pycache__", ".git", "venv"],
            file_extensions=["py", "pyi"]
        )
        
        # Прямая передача в инструмент без преобразований
        file_lister_input = FileListerInput(**input.to_file_lister_dict())
    """
    # === ПАРАМЕТРЫ ИНСТРУМЕНТА (прямая совместимость) ===
    directory: str = Field(".", description="Корневая директория для анализа")
    max_items: Optional[int] = Field(1000, description="Максимальное количество файлов")
    file_extensions: Optional[List[str]] = Field(
        ["py"], 
        description="Расширения файлов для анализа (None = все файлы)"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description=(
            "Шаблоны для исключения (например, ['__pycache__', '.git']). "
            "Автоматически дополняются из флагов include_tests/include_hidden."
        )
    )
    
    # === УДОБНЫЕ ФЛАГИ (высокоуровневые) ===
    include_tests: bool = Field(
        True,
        description=(
            "Включать ли тестовые файлы и директории. "
            "Если False, автоматически добавляет ['test/**', 'tests/**', '*/test/**', '*/tests/**'] "
            "в exclude_patterns."
        )
    )
    include_hidden: bool = Field(
        False,
        description=(
            "Включать ли скрытые файлы и директории (начинающиеся с '.'). "
            "Если False, автоматически добавляет ['.*', '**/.*'] в exclude_patterns."
        )
    )
    include_code_units: bool = Field(
        False,
        description="Включать ли детальную информацию о единицах кода (классы, функции)"
    )
    
    # === ВАЛИДАЦИЯ И ПРЕОБРАЗОВАНИЯ ===
    @model_validator(mode='after')
    def validate_and_enrich_exclude_patterns(self) -> 'AnalyzeProjectInput':
        """
        Автоматическое обогащение exclude_patterns на основе высокоуровневых флагов.
        
        ПРИНЦИП РАБОТЫ:
        1. Если флаги установлены в False — добавляем соответствующие паттерны
        2. Сохраняем пользовательские паттерны без перезаписи
        3. Избегаем дубликатов через множество
        
        ПРИМЕР:
            Исходные данные:
                exclude_patterns = [".git", "__pycache__"]
                include_tests = False
                include_hidden = False
            
            Результат:
                exclude_patterns = [
                    ".git", "__pycache__", 
                    "test/**", "tests/**", "*/test/**", "*/tests/**",
                    ".*", "**/.*"
                ]
        """
        patterns = set(self.exclude_patterns or [])
        
        # Добавляем паттерны для тестов
        if not self.include_tests:
            test_patterns = [
                "test/**", "tests/**", 
                "*/test/**", "*/tests/**",
                "**/test", "**/tests"
            ]
            patterns.update(test_patterns)
        
        # Добавляем паттерны для скрытых файлов
        if not self.include_hidden:
            hidden_patterns = [
                ".*", "**/.*", 
                ".git", ".git/**",
                ".venv", ".venv/**",
                "__pycache__", "__pycache__/**",
                "*.pyc", "*.pyo"
            ]
            patterns.update(hidden_patterns)
        
        # Сохраняем результат (сортируем для консистентности)
        self.exclude_patterns = sorted(patterns) if patterns else None
        return self
    
    @computed_field
    @property
    def to_file_lister_dict(self) -> Dict[str, Any]:
        """
        Преобразование в словарь, совместимый с FileListerInput.
        
        ВОЗВРАЩАЕТ:
            Словарь с параметрами для прямой передачи в FileListerTool
            
        ПРИМЕР:
            input = AnalyzeProjectInput(directory=".", include_tests=False)
            file_lister_input = FileListerInput(**input.to_file_lister_dict)
        """
        return {
            "path": self.directory,
            "recursive": True,
            "max_items": self.max_items,
            "include_files": True,        
            "include_directories": True, 
            "extensions": self.file_extensions
        }

    
    class Config:
        json_schema_extra = {
            "example": {
                "directory": ".",
                "max_depth": 3,
                "file_extensions": ["py"],
                "include_tests": False,
                "include_hidden": False,
                "include_code_units": True
            }
        }


class GetFileCodeUnitsInput(BaseModel):
    """
    Параметры для получения единиц кода из файла.
    
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


class AnalyzeProjectOutput(BaseModel):
    """
    Результат анализа проекта.
    
    Возвращается capability `project_map.analyze_project`.
    
    Поля:
        - success: успешность выполнения
        - project_structure: структура проекта в формате словаря (для сериализации)
        - file_count: количество проанализированных файлов
        - code_unit_count: общее количество найденных единиц кода
        - scan_duration: длительность анализа в секундах
        - error: описание ошибки (если есть)
    """
    success: bool
    project_structure: Dict[str, Any]
    file_count: int
    code_unit_count: int
    scan_duration: float = Field(0.0, ge=0.0, description="Длительность анализа в секундах")
    error: Optional[str] = None


class GetFileCodeUnitsOutput(BaseModel):
    """
    Результат получения единиц кода из файла.
    
    Возвращается capability `project_map.get_file_code_units`.
    
    Поля:
        - success: успешность выполнения
        - file_path: путь к проанализированному файлу
        - code_units: список единиц кода в формате словарей
        - unit_count: количество найденных единиц кода
        - error: описание ошибки (если есть)
    """
    success: bool
    file_path: str
    code_units: List[CodeUnit]
    unit_count: int
    error: Optional[str] = None