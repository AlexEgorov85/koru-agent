from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re


class ToolMetadata(BaseModel):
    """
    Модель метаданных инструмента
    
    Attributes:
        name: Уникальное имя инструмента
        description: Описание инструмента (мин. 10 символов)
        capabilities: Список поддерживаемых операций
        tags: Теги для фильтрации
        version: Версия инструмента (семантическое версионирование)
        requires_config: Ключи конфигурации, необходимые для работы
    """
    name: str = Field(..., description="Уникальное имя инструмента")
    description: str = Field(..., min_length=10, description="Описание инструмента")
    capabilities: List[str] = Field(default_factory=list, description="Список поддерживаемых операций")
    tags: List[str] = Field(default_factory=list, description="Теги для фильтрации")
    version: str = Field("1.0.0", description="Версия инструмента (семантическое версионирование)")
    requires_config: List[str] = Field(default_factory=list, description="Ключи конфигурации, необходимые для работы")
    
    @validator('name')
    def validate_name_format(cls, v):
        """Валидация формата имени инструмента"""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError('Имя инструмента должно начинаться с буквы и содержать только буквы, цифры, дефисы и подчеркивания')
        return v
    
    @validator('version')
    def validate_semver_format(cls, v):
        """Валидация формата семантического версионирования"""
        # Простая проверка формата версии (major.minor.patch)
        if not re.match(r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?(?:\+[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$', v):
            raise ValueError('Версия должна соответствовать формату семантического версионирования (например, 1.0.0)')
        return v