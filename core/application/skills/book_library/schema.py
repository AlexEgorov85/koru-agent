from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime

class AuthorSearchInput(BaseModel):
    """Схема валидации параметров для поиска книг по автору."""
    name_author: Optional[str] = Field(None, description="Имя автора")
    family_author: Optional[str] = Field(None, description="Фамилия автора")
    author_id: Optional[int] = Field(None, description="ID автора")
    
    @validator('name_author', 'family_author', pre=True)
    def validate_names(cls, v):
        if v is None or v == '' or (isinstance(v, str) and v.strip() == ''):
            return None
        return v.strip() if isinstance(v, str) else v
    
    @validator('author_id', pre=True)
    def validate_author_id(cls, v):
        if v is None or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

class FullTextInput(BaseModel):
    """Схема валидации параметров для получения полного текста книги."""
    book_title: Optional[str] = Field(None, description="Название книги")
    book_id: Optional[int] = Field(None, description="ID книги")
    include_metadata: bool = Field(True, description="Включать ли метаданные книги")
    max_chapters: Optional[int] = Field(None, description="Максимальное количество частей для извлечения")
    
    @validator('book_title')
    def validate_book_title(cls, v):
        if v and len(v) > 200:
            raise ValueError("Название книги не может быть длиннее 200 символов")
        return v

class DynamicSQLInput(BaseModel):
    """Схема валидации параметров для динамического SQL запроса."""
    user_question: str = Field(..., description="Вопрос пользователя для генерации SQL")
    context_tables: List[str] = Field(["authors", "books", "chapters", "genres"], description="Таблицы для использования в запросе")
    max_rows: int = Field(50, ge=1, le=100, description="Максимальное количество строк в результате")
    include_reasoning: bool = Field(False, description="Включать ли объяснение для запроса")

class SQLQuery(BaseModel):
    """Схема для валидации SQL запроса."""
    sql: str = Field(..., description="SQL запрос для выполнения")
    reasoning: Optional[str] = Field(None, description="Обоснование запроса")
    tables_used: List[str] = Field(..., description="Таблицы, используемые в запросе")
    
    @validator('sql')
    def validate_sql(cls, v):
        v = v.strip()
        if not v.lower().startswith(("select", "with")):
            raise ValueError("SQL запрос должен начинаться с SELECT или WITH")
        dangerous_keywords = ["delete", "drop", "alter", "truncate", "insert", "update", "create", "grant", "revoke"]
        if any(keyword in v.lower() for keyword in dangerous_keywords):
            raise ValueError("Запрос содержит опасные операции, разрешены только SELECT")
        return v