"""
Схемы данных для библиотеки книг.

Содержит Pydantic-модели, используемые в навыке библиотеки книг.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AuthorSearchInput(BaseModel):
    """Входная схема для поиска по автору."""
    author_name: str = Field(..., description="Имя автора для поиска")
    limit: Optional[int] = Field(10, description="Ограничение на количество результатов")


class FullTextInput(BaseModel):
    """Входная схема для полнотекстового поиска."""
    search_text: str = Field(..., description="Текст для поиска")
    limit: Optional[int] = Field(10, description="Ограничение на количество результатов")


class DynamicSQLInput(BaseModel):
    """Входная схема для динамического SQL-запроса."""
    table_name: str = Field(..., description="Имя таблицы")
    columns: List[str] = Field(..., description="Колонки для выборки")
    conditions: str = Field(..., description="Условия WHERE")
    limit: Optional[int] = Field(None, description="Ограничение на количество результатов")


class SQLQuery(BaseModel):
    """Схема для SQL-запроса."""
    query: str = Field(..., description="SQL-запрос")
    parameters: Optional[dict] = Field(default_factory=dict, description="Параметры запроса")