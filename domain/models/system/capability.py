from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Type
from enum import Enum


class Visibility(Enum):
    """Видимость возможности для включения в промт"""
    PUBLIC = "public"
    PRIVATE = "private"
    HIDDEN = "hidden"


class Capability(BaseModel):
    """
    Capability — единица выбора для LLM.
    
    ПРИНЦИПЫ:
    - Capability знает о типе своих параметров
    - Валидация выполняется на уровне ExecutionGateway
    - Навыки работают с объектами вместо словарей
    """
    #: Уникальное имя capability (используется LLM)
    name: str = Field(..., description="Уникальное имя capability")
    
    #: Человекочитаемое описание
    description: str = Field(..., description="Описание возможности")
    
    #: JSON Schema / Pydantic schema параметров (для обратной совместимости)
    parameters_schema: Dict[str, Any] = Field(..., description="Схема входных параметров")
    
    #: Имя навыка, которому принадлежит capability
    skill_name: str = Field(..., description="Имя навыка")
    
    #: Видимость возможности для включения в промт
    visibility: Visibility = Field(Visibility.PUBLIC, description="Видимость возможности")
    
    #: Дополнительные метаданные
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")