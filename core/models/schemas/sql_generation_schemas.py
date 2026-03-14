"""
Схемы данных для сервиса генерации SQL.

Содержит Pydantic-модели, используемые в сервисе генерации SQL.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SQLGenerationInput(BaseModel):
    """Входная схема для генерации SQL-запроса."""
    natural_language_query: str = Field(..., description="Запрос на естественном языке")
    table_schema: str = Field(..., description="Схема таблицы в текстовом формате")
    required_columns: Optional[List[str]] = Field(default_factory=list, description="Требуемые колонки в результате")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Фильтры для запроса")
    connection_name: Optional[str] = Field(None, description="Имя подключения к базе данных")


class SQLGenerationOutput(BaseModel):
    """Выходная схема для результата генерации SQL-запроса."""
    generated_sql: str = Field(..., description="Сгенерированный SQL-запрос")
    confidence_score: float = Field(..., description="Уровень уверенности в сгенерированном запросе")
    explanation: str = Field(..., description="Объяснение сгенерированного запроса")
    potential_issues: List[str] = Field(default_factory=list, description="Потенциальные проблемы с запросом")


class SQLCorrectionInput(BaseModel):
    """Входная схема для коррекции SQL-запроса."""
    original_query: str = Field(..., description="Оригинальный SQL-запрос")
    error_message: str = Field(..., description="Сообщение об ошибке")
    correction_request: str = Field(..., description="Запрос на коррекцию")
    table_schema: Dict[str, Any] = Field(..., description="Схема таблицы в формате JSON")


class SQLCorrectionOutput(BaseModel):
    """Выходная схема для результата коррекции SQL-запроса."""
    corrected_sql: str = Field(..., description="Исправленный SQL-запрос")
    correction_explanation: str = Field(..., description="Объяснение внесенных изменений")
    confidence_score: float = Field(..., description="Уровень уверенности в исправленном запросе")