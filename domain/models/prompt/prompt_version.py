from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
import json
import re

class PromptStatus(str, Enum):
    """Статусы жизненного цикла промта"""
    DRAFT = "draft"           # Черновик, не готов к использованию
    ACTIVE = "active"         # Активная версия, используется в системе
    SHADOW = "shadow"         # Экспериментальная версия для A/B тестирования
    DEPRECATED = "deprecated" # Устаревшая, но еще работает
    ARCHIVED = "archived"     # Архивированная, больше не используется

class PromptRole(str, Enum):
    """Роль промта в диалоге (соответствует форматам провайдеров)"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class VariableSchema(BaseModel):
    """Схема переменной шаблона"""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    required: bool = True
    description: str = ""
    default_value: Optional[Any] = None
    validation_pattern: Optional[str] = None  # regex для валидации строки

class PromptUsageMetrics(BaseModel):
    """Метрики использования версии промта"""
    usage_count: int = Field(default=0, description="Количество использований")
    success_count: int = Field(default=0, description="Количество успешных использований")
    avg_generation_time: float = Field(default=0.0, description="Среднее время генерации")
    last_used_at: Optional[datetime] = Field(default=None, description="Время последнего использования")
    error_rate: float = Field(default=0.0, description="Процент ошибок")
    rejection_count: int = Field(default=0, description="Количество отклонений валидатором")

class PromptExecutionSnapshot(BaseModel):
    """Снимок выполнения промта"""
    id: str = Field(default_factory=lambda: f"snapshot_{uuid4().hex[:12]}")
    prompt_id: str
    session_id: str
    rendered_prompt: str
    variables: Dict[str, Any]
    response: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    rejection_reason: Optional[str] = None  # Если валидатор отклонил
    provider_response_time: float = 0.0
    
    class Config:
        frozen = True

class PromptVersion(BaseModel):
    """
    Версия промта с полным жизненным циклом и контрактами
    """
    
    # === Идентификация ===
    id: str = Field(default_factory=lambda: f"prompt_{uuid4().hex[:12]}")
    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")  # MAJOR.MINOR.PATCH
    
    # === Адресация ===
    domain: DomainType
    provider_type: LLMProviderType
    capability_name: str
    role: PromptRole
    
    # === Содержимое ===
    content: str = Field(description="Текст промта")
    variables_schema: List[VariableSchema] = Field(
        default_factory=list,
        description="Схема переменных шаблона с валидацией"
    )
    
    # === Контракт вывода ===
    expected_response_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema для валидации ответа"
    )
    
    # === Жизненный цикл ===
    status: PromptStatus = Field(default=PromptStatus.DRAFT, description="Статус жизненного цикла")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activation_date: Optional[datetime] = Field(default=None, description="Дата активации")
    deprecation_date: Optional[datetime] = Field(default=None, description="Дата устаревания")
    archived_date: Optional[datetime] = Field(default=None, description="Дата архивации")
    
    # === История изменений ===
    parent_version_id: Optional[str] = Field(default=None, description="ID родительской версии")
    version_notes: str = Field(default="", description="Описание изменений в версии")
    
    # === Метрики ===
    usage_metrics: PromptUsageMetrics = Field(default_factory=PromptUsageMetrics)
    
    class Config:
        frozen = True  # Иммутабельность
    
    def get_address_key(self) -> str:
        """Ключ для поиска: домен:провайдер:capability:роль"""
        return f"{self.domain.value}:{self.provider_type.value}:{self.capability_name}:{self.role.value}"
    
    def validate_variables(self, variables: Dict[str, Any]) -> Dict[str, List[str]]:
        """Валидация переменных по схеме, возвращает ошибки"""
        errors = {}
        
        for schema_var in self.variables_schema:
            var_name = schema_var.name
            required = schema_var.required
            
            if required and var_name not in variables:
                errors[var_name] = [f"Обязательная переменная '{var_name}' отсутствует"]
                continue
                
            if var_name in variables:
                value = variables[var_name]
                
                # Проверка типа
                expected_type = schema_var.type
                actual_type = type(value).__name__
                
                if expected_type == "string" and not isinstance(value, str):
                    errors.setdefault(var_name, []).append(f"Ожидается строка, получено {actual_type}")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.setdefault(var_name, []).append(f"Ожидается целое число, получено {actual_type}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.setdefault(var_name, []).append(f"Ожидается булево значение, получено {actual_type}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.setdefault(var_name, []).append(f"Ожидается массив, получено {actual_type}")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.setdefault(var_name, []).append(f"Ожидается объект, получено {actual_type}")
                
                # Проверка регулярного выражения для строк
                if expected_type == "string" and schema_var.validation_pattern and isinstance(value, str):
                    if not re.match(schema_var.validation_pattern, value):
                        errors.setdefault(var_name, []).append(f"Значение не соответствует шаблону: {schema_var.validation_pattern}")
        
        return errors