"""
Временные схемы для SQL сервисов.

TODO: Мигрировать на использование контрактов при инициализации сервиса.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SQLGenerationInput(BaseModel):
    """Входная схема для генерации SQL-запроса."""
    natural_language_query: str
    table_schema: str
    required_columns: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    connection_name: Optional[str] = None


class SQLGenerationOutput(BaseModel):
    """Выходная схема для результата генерации SQL-запроса."""
    generated_sql: str
    confidence_score: float
    explanation: str
    potential_issues: Optional[List[str]] = None


class SQLCorrectionInput(BaseModel):
    """Входная схема для коррекции SQL-запроса."""
    original_query: str
    error_message: str
    correction_request: str
    table_schema: Dict[str, Any]


class SQLCorrectionOutput(BaseModel):
    """Выходная схема для результата коррекции SQL-запроса."""
    corrected_sql: str
    correction_explanation: str
    confidence_score: float


class SQLQueryInput(BaseModel):
    """Входная схема для выполнения SQL-запроса."""
    sql_query: str
    parameters: Optional[Dict[str, Any]] = None
    connection_name: Optional[str] = None


class SQLQueryOutput(BaseModel):
    """Выходная схема для результата выполнения SQL-запроса."""
    rows: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time_ms: float