"""
Pydantic-контракты для мета-навыка создания/исправления навыков.

АРХИТЕКТУРА:
- MetaSkillCreateInput: входные параметры для создания навыка
- MetaSkillCreateOutput: сгенерированные артефакты навыка
- MetaSkillFixInput: входные параметры для исправления навыка
- MetaSkillFixOutput: результат исправления
- MetaSkillReviewInput: входные параметры для код-ревью
- MetaSkillReviewOutput: результат код-ревью
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class MetaSkillCreateInput(BaseModel):
    """Входной контракт для meta_skill.create."""
    description: str = Field(
        ...,
        description="Подробное описание логики навыка, его назначения и ожидаемого поведения"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Список имён capabilities, которые должен поддерживать навык"
    )
    dry_run: bool = Field(
        default=True,
        description="Если True — только генерация и валидация без записи файлов"
    )
    target_directory: Optional[str] = Field(
        default=None,
        description="Кастомная директория для размещения файлов навыка"
    )


class GeneratedPythonFile(BaseModel):
    """Описание одного сгенерированного Python-файла."""
    filename: str = Field(..., description="Имя файла, например 'skill.py'")
    content: str = Field(..., description="Содержимое файла")
    file_type: str = Field(
        default="skill",
        description="Тип файла: 'skill', 'handler', 'helper', 'contract'"
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


class MetaSkillCreateOutput(BaseModel):
    """Выходной контракт для meta_skill.create."""
    skill_name: str = Field(..., description="Уникальное имя навыка (snake_case)")
    skill_class_name: str = Field(..., description="Имя класса навыка (PascalCase + Skill)")
    python_files: List[GeneratedPythonFile] = Field(
        default_factory=list,
        description="Сгенерированные Python-файлы"
    )
    yaml_files: List[GeneratedYamlFile] = Field(
        default_factory=list,
        description="Сгенерированные YAML-файлы (промпты и контракты)"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Ошибки валидации (пустой список = всё ок)"
    )
    deployment_path: Optional[str] = Field(
        default=None,
        description="Путь, куда будут записаны файлы (если dry_run=False)"
    )
    is_valid: bool = Field(
        default=False,
        description="Результат валидации всех артефактов"
    )


class MetaSkillFixInput(BaseModel):
    """Входной контракт для meta_skill.fix."""
    skill_name: str = Field(
        ...,
        description="Имя существующего навыка для исправления"
    )
    issue_description: str = Field(
        ...,
        description="Описание проблемы или желаемого улучшения"
    )
    dry_run: bool = Field(
        default=True,
        description="Если True — только генерация исправления без записи"
    )


class MetaSkillFixOutput(BaseModel):
    """Выходной контракт для meta_skill.fix."""
    skill_name: str = Field(..., description="Имя исправляемого навыка")
    original_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Оригинальные файлы (filename -> content)"
    )
    patched_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Исправленные файлы (filename -> content)"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Ошибки валидации исправленных файлов"
    )
    is_valid: bool = Field(
        default=False,
        description="Результат валидации исправленных артефактов"
    )
    change_summary: str = Field(
        default="",
        description="Краткое описание внесённых изменений"
    )


class MetaSkillReviewInput(BaseModel):
    """Входной контракт для meta_skill.review."""
    skill_name: str = Field(
        ...,
        description="Имя навыка для код-ревью"
    )
    review_focus: Optional[List[str]] = Field(
        default=None,
        description="Фокус ревью: ['security', 'architecture', 'style', 'performance']"
    )


class ReviewFinding(BaseModel):
    """Отдельная находка при код-ревью."""
    category: str = Field(
        ...,
        description="Категория: 'security', 'architecture', 'style', 'performance', 'bug'"
    )
    severity: str = Field(
        ...,
        description="Серьёзность: 'critical', 'high', 'medium', 'low'"
    )
    file: str = Field(..., description="Файл, в котором найдена проблема")
    line_hint: Optional[str] = Field(
        default=None,
        description="Подсказка о расположении проблемы"
    )
    description: str = Field(..., description="Описание проблемы")
    suggestion: str = Field(..., description="Рекомендация по исправлению")


class MetaSkillReviewOutput(BaseModel):
    """Выходной контракт для meta_skill.review."""
    skill_name: str = Field(..., description="Имя просмотренного навыка")
    overall_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Общая оценка качества кода (0-100)"
    )
    findings: List[ReviewFinding] = Field(
        default_factory=list,
        description="Список найденных проблем"
    )
    summary: str = Field(
        default="",
        description="Общее резюме ревью"
    )
    passed: bool = Field(
        default=False,
        description="Прошёл ли навык ревью (нет critical/high проблем)"
    )
