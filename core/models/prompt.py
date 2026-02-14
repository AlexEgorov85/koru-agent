from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import List, Optional, Dict, Literal
from datetime import datetime
import re


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PromptMetadata(BaseModel):
    version: str = Field(..., pattern=r"^v?\d+\.\d+\.\d+$")
    skill: str
    capability: str
    strategy: Optional[str] = None  # null = все стратегии
    role: Literal["system", "user", "assistant"] = "system"
    language: str = "ru"
    tags: List[str] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)
    status: PromptStatus = PromptStatus.DRAFT
    quality_metrics: Optional[Dict[str, float]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    author: str
    changelog: List[str] = Field(default_factory=list)

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v):
        if not re.match(r"^v?\d+\.\d+\.\d+$", v):
            raise ValueError("Version must follow semantic versioning format (e.g., '1.0.0' or 'v1.0.0')")
        return v


class Prompt(BaseModel):
    metadata: PromptMetadata
    content: str = Field(..., min_length=10)

    @field_validator('content')
    @classmethod
    def validate_content_variables(cls, v, values):
        """Проверяет, что все переменные в content соответствуют объявленным в metadata.variables"""
        if 'metadata' in values.data:
            metadata = values.data['metadata']
            if metadata and metadata.variables:
                # Ищем все переменные в формате {{ variable }}
                content_vars = re.findall(r'\{\{\s*(\w+)\s*\}\}', v)

                # Проверяем, что все переменные в content объявлены в metadata.variables
                for var in content_vars:
                    if var not in metadata.variables:
                        raise ValueError(f"Variable '{var}' used in content but not declared in metadata.variables")

                # Проверяем, что все объявленные переменные используются в content
                for var in metadata.variables:
                    if not re.search(r'\{\{\s*' + re.escape(var) + r'\s*\}\}', v):
                        raise ValueError(f"Declared variable '{var}' is not used in content")

        return v