"""
Pydantic-контракты для мета-навыка создания/исправления компонентов.

АРХИТЕКТУРА:
- Поддержка всех типов: skill, tool, service, behavior
- component_type определяет структуру, базовый класс и директорию
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


VALID_COMPONENT_TYPES = ["skill", "tool", "service", "behavior"]

TYPE_SUFFIXES = {
    "skill": "Skill",
    "tool": "Tool",
    "service": "Service",
    "behavior": "Pattern",
}

TYPE_FILE_NAMES = {
    "skill": "skill.py",
    "tool": None,
    "service": "service.py",
    "behavior": "pattern.py",
}


class MetaComponentCreateInput(BaseModel):
    """Входной контракт для создания любого типа компонента."""
    description: str = Field(
        ...,
        description="Подробное описание логики компонента, его назначения и ожидаемого поведения"
    )
    component_type: str = Field(
        default="skill",
        description="Тип компонента: 'skill', 'tool', 'service', 'behavior'"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Список имён capabilities, которые должен поддерживать компонент"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Список зависимостей (имена других компонентов)"
    )
    has_prompts: bool = Field(
        default=True,
        description="Нужны ли промпты (True для skill/behavior, False для tool)"
    )
    has_contracts: bool = Field(
        default=True,
        description="Нужны ли контракты input/output"
    )


class GeneratedPythonFile(BaseModel):
    """Описание одного сгенерированного Python-файла."""
    filename: str = Field(..., description="Имя файла, например 'skill.py' или 'my_tool.py'")
    content: str = Field(..., description="Содержимое файла")
    file_type: str = Field(
        default="main",
        description="Тип файла: 'main', 'handler', 'helper', 'input_output'"
    )


class GeneratedYamlFile(BaseModel):
    """Описание одного сгенерированного YAML-файла."""
    filename: str = Field(..., description="Имя файла, например 'create.user_v1.0.0.yaml'")
    content: str = Field(..., description="Содержимое YAML")
    file_category: str = Field(
        default="prompt",
        description="Категория: 'prompt' или 'contract'"
    )
    direction: Optional[str] = Field(
        default=None,
        description="Для контрактов: 'input' или 'output'"
    )


class MetaComponentCreateOutput(BaseModel):
    """Выходной контракт для создания компонента."""
    component_name: str = Field(..., description="Уникальное имя компонента (snake_case)")
    component_type: str = Field(..., description="Тип: 'skill', 'tool', 'service', 'behavior'")
    class_name: str = Field(..., description="Имя класса (PascalCase + суффикс типа)")
    python_files: List[GeneratedPythonFile] = Field(
        default_factory=list,
        description="Сгенерированные Python-файлы"
    )
    yaml_files: List[GeneratedYamlFile] = Field(
        default_factory=list,
        description="Сгенерированные YAML-файлы (промпты и контракты)"
    )
    is_valid: bool = Field(default=False, description="Результат валидации")
    validation_errors: List[str] = Field(default_factory=list)


class MetaComponentFixInput(BaseModel):
    """Входной контракт для исправления компонента."""
    component_name: str = Field(..., description="Имя существующего компонента")
    component_type: str = Field(
        default="skill",
        description="Тип компонента: 'skill', 'tool', 'service', 'behavior'"
    )
    issue_description: str = Field(
        ...,
        description="Описание проблемы или желаемого улучшения"
    )


class MetaComponentFixOutput(BaseModel):
    """Выходной контракт для исправления компонента."""
    component_name: str = Field(..., description="Имя исправляемого компонента")
    component_type: str = Field(..., description="Тип компонента")
    patched_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Исправленные файлы (filename -> content)"
    )
    is_valid: bool = Field(default=False)
    validation_errors: List[str] = Field(default_factory=list)
    change_summary: str = Field(default="")


class MetaComponentReviewInput(BaseModel):
    """Входной контракт для код-ревью компонента."""
    component_name: str = Field(..., description="Имя компонента для код-ревью")
    component_type: str = Field(
        default="skill",
        description="Тип компонента: 'skill', 'tool', 'service', 'behavior'"
    )
    review_focus: Optional[List[str]] = Field(
        default=None,
        description="Фокус ревью: ['security', 'architecture', 'style', 'performance']"
    )


class ReviewFinding(BaseModel):
    """Отдельная находка при код-ревью."""
    category: str = Field(..., description="Категория: 'security', 'architecture', 'style', 'performance', 'bug'")
    severity: str = Field(..., description="Серьёзность: 'critical', 'high', 'medium', 'low'")
    file: str = Field(..., description="Файл, в котором найдена проблема")
    line_hint: Optional[str] = Field(default=None, description="Подсказка о расположении")
    description: str = Field(..., description="Описание проблемы")
    suggestion: str = Field(..., description="Рекомендация по исправлению")


class MetaComponentReviewOutput(BaseModel):
    """Выходной контракт для код-ревью компонента."""
    component_name: str = Field(..., description="Имя просмотренного компонента")
    component_type: str = Field(..., description="Тип компонента")
    overall_score: int = Field(..., ge=0, le=100, description="Общая оценка качества кода (0-100)")
    findings: List[ReviewFinding] = Field(default_factory=list)
    summary: str = Field(default="", description="Общее резюме ревью")
    passed: bool = Field(default=False, description="Прошёл ли компонент ревью")
