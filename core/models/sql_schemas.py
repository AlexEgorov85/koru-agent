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
    available_scripts: Optional[str] = None
    available_tables: Optional[str] = None


class SQLGenerationOutput(BaseModel):
    """Выходная схема для результата генерации SQL-запроса с самоанализом."""
    analysis_understanding: str = Field(description="1. Понимание запроса: Какие сущности, условия и связи упоминаются пользователем?")
    analysis_schema: str = Field(description="2. Анализ схемы: Какие таблицы и колонки требуются?")
    analysis_strategy: str = Field(description="3. Выбор стратегии: Будет ли это простой SELECT, агрегация, подзапрос или CTE?")
    analysis_validation: str = Field(description="4. Валидация параметров: Все ли условия учтены?")
    analysis_security: str = Field(description="5. Безопасность: Соответствует ли запрос политике SELECT-ONLY?")
    analysis_optimization: str = Field(description="6. Оптимизация: Можно ли улучшить производительность?")
    generated_sql: str = Field(description="Сгенерированный SQL-запрос. ТОЛЬКО код, без markdown.")
    confidence_score: float = Field(description="7. Оценка уверенности (0.0-1.0)", ge=0.0, le=1.0)
    potential_issues: Optional[List[str]] = Field(default_factory=list, description="8. Потенциальные проблемы")
    final_check: str = Field(description="9. Финальная проверка: соответствует ли SQL запросу?")


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