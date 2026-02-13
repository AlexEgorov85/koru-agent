from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SQLQueryInput(BaseModel):
    """Входные данные для выполнения SQL-запроса"""
    user_question: str
    tables: List[str]
    max_rows: int = 50
    context: Optional[str] = None


class SQLQueryOutput(BaseModel):
    """Выходные данные выполнения SQL-запроса"""
    success: bool
    rows: List[Dict[str, Any]]
    columns: List[str]
    rowcount: int
    error: Optional[str] = None
    query_executed: str = ""
    execution_time: Optional[float] = None