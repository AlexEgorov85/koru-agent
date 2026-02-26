"""
Схемы данных для сервиса SQL-запросов.

Содержит Pydantic-модели, используемые в сервисе SQL-запросов.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SQLQueryInput(BaseModel):
    """Входная схема для SQL-запроса."""
    query: str = Field(..., description="SQL-запрос для выполнения")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Параметры запроса")
    connection_name: Optional[str] = Field(None, description="Имя подключения к базе данных")


class SQLQueryOutput(BaseModel):
    """Выходная схема для результата SQL-запроса."""
    rows: List[Dict[str, Any]] = Field(..., description="Результаты запроса в виде списка словарей")
    row_count: int = Field(..., description="Количество возвращенных строк")
    column_names: List[str] = Field(..., description="Имена колонок результата")
    execution_time_ms: Optional[float] = Field(None, description="Время выполнения запроса в миллисекундах")