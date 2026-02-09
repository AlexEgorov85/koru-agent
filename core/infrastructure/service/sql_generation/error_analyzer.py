from typing import Dict, Any, Optional
from dataclasses import dataclass
from core.system_context.base_system_contex import BaseSystemContext
from core.infrastructure.service.base_service import BaseService, ServiceInput, ServiceOutput
import re

@dataclass
class ExecutionError:
    """Структура для представления ошибки выполнения SQL-запроса"""
    message: str
    query: str
    parameters: Dict[str, Any]
    db_error_type: str  # syntax_error, permission_error, schema_error, timeout_error, other_error

class SQLErrorAnalyzer(BaseService):
    """
    Анализатор ошибок выполнения SQL-запросов.
    
    ФУНКЦИОНАЛЬНОСТЬ:
    1. Классификация типа ошибки (синтаксис, семантика, права доступа)
    2. Извлечение информации о таблицах, вызвавших ошибку
    3. Формирование рекомендаций по исправлению
    4. Определение возможности автоматической коррекции
    """
    
    @property
    def description(self) -> str:
        return "Анализатор ошибок выполнения SQL-запросов"
    
    def __init__(self, system_context: BaseSystemContext):
        super().__init__(system_context, "sql_error_analyzer")
        self.error_patterns = {
            "syntax_error": [
                r"syntax error",
                r"parser.*error",
                r"missing.*operator",
                r"extra.*data",
                r"invalid.*input",
                r"unexpected.*token"
            ],
            "schema_error": [
                r"relation.*does not exist",
                r"column.*does not exist",
                r"table.*not found",
                r"column.*not found",
                r"ambiguous column",
                r"relation.*already exists"
            ],
            "permission_error": [
                r"permission denied",
                r"access denied",
                r"insufficient privileges",
                r"no.*rights"
            ],
            "timeout_error": [
                r"timeout",
                r"query.*canceled",
                r"statement.*timeout"
            ]
        }
    
    async def initialize(self) -> bool:
        """Инициализация анализатора ошибок"""
        self.logger.info("SQLErrorAnalyzer успешно инициализирован")
        return True
    
    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """Выполнение анализа ошибки - в данном случае не используется напрямую"""
        # Этот метод не используется напрямую, так как анализатор ошибок используется через метод analyze
        raise NotImplementedError("SQLErrorAnalyzer не поддерживает прямое выполнение. Используйте метод analyze()")
    
    async def shutdown(self) -> None:
        """Завершение работы анализатора ошибок"""
        self.logger.info("Завершение работы SQLErrorAnalyzer")
    
    async def analyze(self, error: ExecutionError) -> Dict[str, Any]:
        """
        Анализ ошибки выполнения SQL-запроса.
        
        ВОЗВРАЩАЕТ:
        - Тип ошибки (syntax_error, schema_error, permission_error, timeout_error, other_error)
        - Таблицы, участвующие в запросе
        - Предложения по исправлению
        - Уверенность в анализе (0.0-1.0)
        """
        error_type = self._classify_error(error.message)
        tables_involved = self._extract_tables_from_query(error.query)
        suggested_fix = self._suggest_fix(error_type, error.message, tables_involved)
        confidence = self._calculate_confidence(error_type, error.message)
        
        return {
            "error_type": error_type,
            "tables_involved": tables_involved,
            "suggested_fix": suggested_fix,
            "confidence": confidence,
            "raw_error": error.message
        }
    
    def _classify_error(self, error_message: str) -> str:
        """Классификация типа ошибки по сообщению"""
        error_lower = error_message.lower()
        
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return error_type
        
        return "other_error"
    
    def _extract_tables_from_query(self, query: str) -> list:
        """Извлечение имен таблиц из SQL-запроса"""
        # Простая реализация - в реальном проекте использовать SQL-парсер
        # Ищем имена таблиц после FROM и JOIN
        table_pattern = r'(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
        matches = re.findall(table_pattern, query, re.IGNORECASE)
        
        # Убираем дубликаты и ключевые слова
        tables = []
        for match in matches:
            clean_match = match.strip().lower()
            if clean_match not in ['select', 'where', 'and', 'or', 'order', 'by', 'group', 'having']:
                if clean_match not in tables:
                    tables.append(clean_match)
        
        return tables
    
    def _suggest_fix(self, error_type: str, error_message: str, tables_involved: list) -> Optional[str]:
        """Предложение способа исправления ошибки"""
        if error_type == "syntax_error":
            return "Проверьте синтаксис SQL-запроса, возможно, пропущены запятые, скобки или ключевые слова."
        elif error_type == "schema_error":
            if "does not exist" in error_message.lower():
                table_name = self._extract_problematic_table(error_message)
                if table_name:
                    return f"Проверьте существование таблицы или колонки '{table_name}'. Возможно, она была удалена или переименована."
                else:
                    return "Проверьте существование указанных таблиц и колонок в базе данных."
            elif "ambiguous column" in error_message.lower():
                return "Укажите полное имя колонки с префиксом таблицы или алиаса, так как колонка встречается в нескольких таблицах."
        elif error_type == "permission_error":
            return "Проверьте права доступа к базе данных и таблицам. Возможно, требуется предоставить дополнительные разрешения."
        elif error_type == "timeout_error":
            return "Добавьте условия фильтрации или ограничьте количество возвращаемых записей с помощью LIMIT."
        else:
            return "Проверьте запрос и данные, возможно, проблема связана с содержимым данных или ограничениями схемы."
    
    def _extract_problematic_table(self, error_message: str) -> Optional[str]:
        """Извлечение имени таблицы из сообщения об ошибке"""
        # Ищем имя таблицы в сообщении об ошибке
        patterns = [
            r"relation \"?([^\"]+)\"? does not exist",
            r"table \"?([^\"]+)\"? not found",
            r"column \"?([^\"]+)\"? does not exist",
            r"class \"?([^\"]+)\"? not found"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _calculate_confidence(self, error_type: str, error_message: str) -> float:
        """Расчет уверенности в классификации ошибки"""
        # Простая эвристика - в реальном проекте использовать ML
        confidence = 0.7  # Базовая уверенность
        
        # Повышаем уверенность для четко определенных ошибок
        if error_type in ["syntax_error", "permission_error", "timeout_error"]:
            confidence = 0.9
        elif error_type == "schema_error":
            confidence = 0.85
        
        # Понижаем, если сообщение об ошибке слишком общее
        if len(error_message) < 20:
            confidence -= 0.1
        
        return max(0.5, min(1.0, confidence))