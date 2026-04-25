"""
SQL Validator Service - Валидация SQL-запросов перед выполнением.
"""
from typing import Dict, Any, Optional, List
from core.components.base_component import BaseComponent
from core.models.component_meta import ComponentType


class SQLValidatorService(BaseComponent):
    """Сервис валидации SQL-запросов."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialized = False

    async def initialize(self) -> bool:
        """Инициализация сервиса."""
        try:
            self.log.info("Инициализация SQLValidatorService...")
            self._initialized = True
            self.log.info("SQLValidatorService успешно инициализирован")
            return True
        except Exception as e:
            self.log.error(f"Ошибка инициализации SQLValidatorService: {e}", exc_info=True)
            return False

    def is_initialized(self) -> bool:
        """Проверка инициализации."""
        return self._initialized

    async def validate_input(self, natural_language_query: str, table_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Валидация входных данных для генерации SQL.
        
        Args:
            natural_language_query: Запрос на естественном языке
            table_schema: Опциональная схема таблиц
            
        Returns:
            Dict с результатами валидации
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "safety_score": 1.0
        }
        
        # Проверка пустого запроса
        if not natural_language_query or not natural_language_query.strip():
            result["is_valid"] = False
            result["errors"].append("Запрос не может быть пустым")
            result["safety_score"] = 0.0
            return result
        
        # Проверка на потенциально опасные паттерны (базовая)
        dangerous_patterns = [
            "DROP TABLE", "DELETE FROM", "TRUNCATE", 
            "ALTER TABLE", "CREATE USER", "GRANT", "REVOKE"
        ]
        
        query_upper = natural_language_query.upper()
        for pattern in dangerous_patterns:
            if pattern in query_upper:
                result["warnings"].append(f"Обнаружен потенциально опасный паттерн: {pattern}")
                result["safety_score"] = max(0.0, result["safety_score"] - 0.3)
        
        return result

    async def validate_sql(self, sql: str, allowed_operations: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Валидация сгенерированного SQL-запроса.
        
        Args:
            sql: SQL-запрос для валидации
            allowed_operations: Список разрешённых операций (SELECT, INSERT, UPDATE, etc.)
            
        Returns:
            Dict с результатами валидации
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "safety_score": 1.0,
            "sql_type": None
        }
        
        if not sql or not sql.strip():
            result["is_valid"] = False
            result["errors"].append("SQL-запрос не может быть пустым")
            result["safety_score"] = 0.0
            return result
        
        sql_upper = sql.strip().upper()
        
        # Определение типа запроса
        if sql_upper.startswith("SELECT"):
            result["sql_type"] = "SELECT"
        elif sql_upper.startswith("INSERT"):
            result["sql_type"] = "INSERT"
        elif sql_upper.startswith("UPDATE"):
            result["sql_type"] = "UPDATE"
        elif sql_upper.startswith("DELETE"):
            result["sql_type"] = "DELETE"
        elif sql_upper.startswith("CREATE"):
            result["sql_type"] = "CREATE"
        elif sql_upper.startswith("DROP"):
            result["sql_type"] = "DROP"
        elif sql_upper.startswith("ALTER"):
            result["sql_type"] = "ALTER"
        else:
            result["sql_type"] = "UNKNOWN"
            result["warnings"].append("Неизвестный тип SQL-запроса")
        
        # Проверка разрешённых операций
        if allowed_operations and result["sql_type"]:
            if result["sql_type"] not in allowed_operations:
                result["is_valid"] = False
                result["errors"].append(f"Операция {result['sql_type']} не разрешена")
                result["safety_score"] = 0.0
                return result
        
        # Проверка на опасные операции
        dangerous_operations = ["DROP", "TRUNCATE", "DELETE WITHOUT WHERE"]
        for op in dangerous_operations:
            if op in sql_upper:
                if "WHERE" not in sql_upper and "DELETE" in sql_upper:
                    result["warnings"].append("DELETE без WHERE clause - опасно!")
                    result["safety_score"] = max(0.0, result["safety_score"] - 0.5)
                elif op in ["DROP", "TRUNCATE"]:
                    result["warnings"].append(f"Опасная операция: {op}")
                    result["safety_score"] = max(0.0, result["safety_score"] - 0.7)
        
        # Базовая проверка синтаксиса (наличие баланса скобок)
        if sql.count("(") != sql.count(")"):
            result["warnings"].append("Возможная ошибка: несбалансированные скобки")
            result["safety_score"] = max(0.0, result["safety_score"] - 0.2)
        
        return result

    async def shutdown(self):
        """Закрытие сервиса."""
        self.log.info("Закрытие SQLValidatorService...")
        self._initialized = False
