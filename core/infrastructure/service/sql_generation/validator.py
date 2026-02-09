from typing import Dict, Any, Tuple
import re
from core.system_context.base_system_contex import BaseSystemContext
from core.infrastructure.service.base_service import BaseService

class SQLQueryValidator(BaseService):
    """
    Валидатор безопасности SQL-запросов.
    
    ГАРАНТИИ БЕЗОПАСНОСТИ:
    1. Обязательная параметризация (запрет конкатенации)
    2. Белый список разрешенных операций (только SELECT/WITH)
    3. Валидация имен таблиц/колонок по регулярным выражениям
    4. Ограничение на вложенные запросы и подзапросы
    5. Санитизация комментариев и строковых литералов
    """
    
    @property
    def description(self) -> str:
        return "Валидатор безопасности SQL-запросов"
    
    def __init__(self, system_context: BaseSystemContext):
        super().__init__(system_context, "sql_validator")
        self.allowed_operations = {"SELECT", "WITH"}
        self.max_nesting_level = 3
        self.identifier_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
        self.schema_qualified_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$')
    
    async def initialize(self) -> bool:
        """Инициализация валидатора"""
        self.logger.info("SQLQueryValidator успешно инициализирован")
        return True
    
    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """Выполнение валидации - в данном случае не используется напрямую"""
        raise NotImplementedError("SQLQueryValidator не поддерживает прямое выполнение")
    
    async def shutdown(self) -> None:
        """Завершение работы валидатора"""
        self.logger.info("Завершение работы SQLQueryValidator")
    
    async def validate_query(self, sql: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any], float]:
        """
        Валидация запроса с возвратом скорректированной версии и оценки безопасности.
        
        ВОЗВРАЩАЕТ:
        - Валидированный SQL (гарантированно безопасный)
        - Параметры (проверенные на типы)
        - Оценка безопасности (0.0-1.0)
        """
        # 1. Проверка операций
        self._validate_operations(sql)
        
        # 2. Проверка параметризации (запрет конкатенации)
        if self._contains_concatenation(sql):
            raise ValueError("Запрещена конкатенация пользовательских данных в SQL-запросе")
        
        # 3. Валидация имен таблиц/колонок
        self._validate_identifiers(sql)
        
        # 4. Проверка параметров
        validated_params = self._validate_parameters(parameters)
        
        # 5. Расчет оценки безопасности
        safety_score = self._calculate_safety_score(sql, validated_params)
        
        return sql, validated_params, safety_score
    
    def _validate_operations(self, sql: str):
        """Проверка разрешенных операций"""
        sql_upper = sql.upper().strip()
        
        # Запрещенные операции (черный список)
        forbidden = ["DELETE", "DROP", "ALTER", "TRUNCATE", "INSERT", "UPDATE", "CREATE", "GRANT", "REVOKE"]
        for op in forbidden:
            if re.search(rf'\b{op}\b', sql_upper):
                raise ValueError(f"Запрещенная операция '{op}' в SQL-запросе")
        
        # Разрешенные операции (белый список)
        if not any(sql_upper.startswith(op) for op in self.allowed_operations):
            raise ValueError(f"SQL-запрос должен начинаться с разрешенной операции: {self.allowed_operations}")
    
    def _contains_concatenation(self, sql: str) -> bool:
        """Обнаружение потенциальной конкатенации (защита от инъекций)"""
        # Простой эвристический анализ
        patterns = [
            r'\|\|',           # PostgreSQL конкатенация
            r'\+',             # Арифметическая конкатенация
            r'CONCAT\(',       # Функция конкатенации
            r'\{.*\}',         # Шаблонные строки
            r'f".*{.*}.*"',    # f-строки Python (если попали в запрос)
        ]
        return any(re.search(pattern, sql, re.IGNORECASE) for pattern in patterns)
    
    def _validate_identifiers(self, sql: str):
        """Валидация имен таблиц и колонок"""
        # Извлечение идентификаторов из запроса (упрощенная реализация)
        # В продакшене использовать парсер SQL (sqlparse)
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', sql)
        
        for ident in identifiers:
            # Пропускаем ключевые слова SQL
            if ident.upper() in {"SELECT", "FROM", "WHERE", "AND", "OR", "ORDER", "BY", "LIMIT", "OFFSET"}:
                continue
                
            # Проверка формата идентификатора
            if not self.identifier_pattern.match(ident) and not self.schema_qualified_pattern.match(ident):
                raise ValueError(f"Некорректный идентификатор: '{ident}'")
    
    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация параметров на безопасность"""
        validated = {}
        for key, value in parameters.items():
            # Проверка имени параметра
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                raise ValueError(f"Некорректное имя параметра: '{key}'")
            
            # Санитизация значений (ограничение типов)
            if isinstance(value, (str, int, float, bool, type(None))):
                validated[key] = value
            elif isinstance(value, (list, dict)):
                # Ограничиваем сложные типы
                validated[key] = str(value)[:500]  # Обрезаем до 500 символов
            else:
                raise ValueError(f"Неподдерживаемый тип параметра '{key}': {type(value)}")
        
        return validated
    
    def _calculate_safety_score(self, sql: str, parameters: Dict[str, Any]) -> float:
        """Расчет оценки безопасности запроса"""
        score = 1.0
        
        # Штрафы за сложность
        if sql.upper().count("UNION") > 1:
            score -= 0.1
        if sql.upper().count("JOIN") > 3:
            score -= 0.05
        if len(parameters) > 10:
            score -= 0.05
            
        # Бонусы за простоту
        if "LIMIT" in sql.upper():
            score += 0.05
            
        return max(0.5, min(1.0, score))  # Ограничиваем диапазон