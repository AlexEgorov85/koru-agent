from pydantic import BaseModel, Field, validator
from typing import List
import re


class SkillMetadata(BaseModel):
    """
    Модель метаданных навыка
    
    Attributes:
        name: Уникальное имя навыка
        description: Описание навыка
        category: Категория навыка (например, "code_analysis", "file_operations")
        required_tools: Имена обязательных инструментов
        optional_tools: Имена опциональных инструментов
        version: Версия навыка (семантическое версионирование)
    """
    name: str = Field(..., description="Уникальное имя навыка")
    description: str = Field(..., min_length=10, description="Описание навыка")
    category: str = Field(..., description="Категория навыка")
    required_tools: List[str] = Field(default_factory=list, description="Имена обязательных инструментов")
    optional_tools: List[str] = Field(default_factory=list, description="Имена опциональных инструментов")
    version: str = Field("1.0.0", description="Версия навыка (семантическое версионирование)")
    
    @validator('name')
    def validate_name_format(cls, v):
        """Валидация формата имени навыка"""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError('Имя навыка должно начинаться с буквы и содержать только буквы, цифры, дефисы и подчеркивания')
        return v
    
    @validator('version')
    def validate_semver_format(cls, v):
        """Валидация формата семантического версионирования"""
        # Простая проверка формата версии (major.minor.patch)
        if not re.match(r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?(?:\+[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$', v):
            raise ValueError('Версия должна соответствовать формату семантического версионирования (например, 1.0.0)')
        return v