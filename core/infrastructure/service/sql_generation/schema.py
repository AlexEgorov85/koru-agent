from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re

class SQLGenerationInput(BaseModel):
    """Входные данные для генерации SQL"""
    user_question: str = Field(..., min_length=5, max_length=1000, description="Вопрос пользователя для генерации запроса")
    tables: List[str] = Field(..., min_items=1, max_items=10, description="Список таблиц для использования (формат: schema.table или table)")
    context: Optional[str] = Field(None, max_length=2000, description="Дополнительный контекст для генерации")
    max_rows: int = Field(100, ge=1, le=1000, description="Максимальное количество строк в результате")
    
    @field_validator('tables')
    @classmethod
    def validate_table_names(cls, v):
        pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')
        for table in v:
            if not pattern.match(table):
                raise ValueError(f"Некорректное имя таблицы: '{table}'")
        return v

class SQLGenerationOutput(BaseModel):
    """Выходные данные генерации SQL (для валидации ответа LLM)"""
    sql: str = Field(..., description="Сгенерированный SQL-запрос (только параметризованный!)")
    reasoning: str = Field(..., min_length=20, max_length=1000, description="Обоснование выбора запроса")
    tables_used: List[str] = Field(..., min_items=1, description="Таблицы, использованные в запросе")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры для параметризованного запроса")
    
    @field_validator('sql')
    @classmethod
    def validate_sql_safety(cls, v):
        # Базовая проверка на отсутствие опасных операций
        v_upper = v.upper()
        forbidden = ["DELETE", "DROP", "ALTER", "TRUNCATE", "INSERT", "UPDATE", "CREATE"]
        if any(op in v_upper for op in forbidden):
            raise ValueError("Запрос содержит запрещенные операции")
        if not v_upper.strip().startswith(("SELECT", "WITH")):
            raise ValueError("Запрос должен начинаться с SELECT или WITH")
        return v

class SQLCorrectionInput(BaseModel):
    """Входные данные для коррекции запроса"""
    original_query: str = Field(..., description="Оригинальный запрос с ошибкой")
    error_message: str = Field(..., max_length=1000, description="Сообщение об ошибке")
    error_type: str = Field(..., description="Тип ошибки (syntax_error, permission_error, schema_error, timeout_error, other_error)")
    suggested_fix: Optional[str] = Field(None, max_length=500, description="Предложенный фикс от анализатора ошибок")
    tables: List[str] = Field(default_factory=list, description="Таблицы, участвующие в запросе")
    context: Optional[str] = Field(None, max_length=2000, description="Контекст выполнения")

class SQLCorrectionOutput(BaseModel):
    """Выходные данные коррекции (для валидации ответа LLM)"""
    corrected_sql: str = Field(..., description="Исправленный SQL-запрос")
    reasoning: str = Field(..., min_length=20, max_length=1000, description="Обоснование исправления")
    tables_used: Optional[List[str]] = Field(None, description="Таблицы в исправленном запросе")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Уверенность в корректности исправления")