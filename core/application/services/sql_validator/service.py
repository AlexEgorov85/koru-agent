from typing import Dict, Any, List, Optional
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.application.context.application_context import ApplicationContext
import re
import sqlparse


class SQLValidatorServiceInput(ServiceInput):
    """Входные данные для SQLValidatorService"""
    def __init__(self, sql_query: str, parameters: Dict[str, Any] = None):
        self.sql_query = sql_query
        self.parameters = parameters or {}


class SQLValidatorServiceOutput(ServiceOutput):
    """Выходные данные для SQLValidatorService"""
    def __init__(self, is_valid: bool, validation_errors: List[str] = None, sanitized_query: str = "", parameters: Dict[str, Any] = None):
        self.is_valid = is_valid
        self.validation_errors = validation_errors or []
        self.sanitized_query = sanitized_query
        self.parameters = parameters or {}


class ValidatedSQL:
    """Результат валидации SQL-запроса"""
    def __init__(self, sql: str, parameters: Dict[str, Any], is_valid: bool, validation_errors: List[str] = None, safety_score: float = 0.0):
        self.sql = sql
        self.parameters = parameters
        self.is_valid = is_valid
        self.validation_errors = validation_errors or []
        self.safety_score = safety_score  # 0.0-1.0 оценка безопасности


class SQLValidatorService(BaseService):
    """
    Сервис для валидации SQL-запросов.

    ФУНКЦИИ:
    - Проверка синтаксиса SQL
    - Проверка на потенциальные SQL-инъекции
    - Проверка разрешенных операций (например, только SELECT)
    - Санитизация и параметризация запросов
    """
    
    # Зависит только от метаданных таблиц
    DEPENDENCIES = ["table_description_service"]  # Зависит только от метаданных таблиц

    @property
    def description(self) -> str:
        return "Сервис для валидации SQL-запросов с проверкой безопасности и параметризацией"

    def __init__(self, application_context: ApplicationContext, name: str = "sql_validator_service", component_config=None, executor=None, allowed_operations: List[str] = None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="sql_validator_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # НЕ загружаем зависимости здесь! Только инициализация внутреннего состояния
        self.allowed_operations = set(allowed_operations or ["SELECT"])

        # Дополнительные настройки безопасности
        self.max_nesting_level = 3
        self.identifier_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
        self.schema_qualified_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$')

        # Компилируем регулярные выражения для обнаружения потенциальных угроз
        self._dangerous_patterns = [
            re.compile(r"(?i)(drop|delete|insert|update|truncate|alter|create|exec|execute)", re.IGNORECASE),
            re.compile(r"(?i)(union\s+select|waitfor\s+delay|benchmark\(|sleep\()", re.IGNORECASE),
            re.compile(r"'[^']*'.*['\"];", re.IGNORECASE),  # потенциальные инъекции
        ]

    async def _custom_initialize(self) -> bool:
        """Инициализация сервиса"""
        try:
            # Зависимости уже загружены родительским методом
            # Доступны через: self.table_description_service_instance

            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    f"SQLValidatorService инициализирован с разрешенными операциями: {self.allowed_operations}"
                )
            return True
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка инициализации SQLValidatorService: {str(e)}")
            return False

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса валидации SQL."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.PROVIDER_REGISTERED

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса валидации SQL (СИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Валидация SQL-запроса (синхронный вызов)
        result = self.validate_query(parameters.get("sql", ""), parameters.get("parameters"))
        return {
            "is_valid": result.is_valid,
            "validation_errors": result.validation_errors,
            "sanitized_sql": result.sanitized_sql,
            "capability": capability.name
        }

    def validate_query(self, sql_query: str, parameters: Dict[str, Any] = None) -> ValidatedSQL:
        """
        Валидация SQL-запроса на безопасность и корректность (СИНХРОННАЯ).

        ARGS:
        - sql_query: строка SQL-запроса для валидации
        - parameters: параметры запроса

        RETURNS:
        - ValidatedSQL: результат валидации с оценкой безопасности
        """
        validation_errors = []
        parameters = parameters or {}

        # 1. Проверка синтаксиса
        try:
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                validation_errors.append("Невозможно распарсить SQL-запрос")
        except Exception as e:
            validation_errors.append(f"Ошибка парсинга SQL: {str(e)}")

        # 2. Проверка разрешенных операций
        try:
            self._validate_operations(sql_query)
        except ValueError as e:
            validation_errors.append(str(e))

        # 3. Проверка параметризации (запрет конкатенации)
        try:
            if self._contains_concatenation(sql_query):
                validation_errors.append("Запрещена конкатенация пользовательских данных в SQL-запросе")
        except ValueError as e:
            validation_errors.append(str(e))
        
        # 4. Валидация имен таблиц/колонок
        try:
            self._validate_identifiers(sql_query)
        except ValueError as e:
            validation_errors.append(str(e))
        
        # 5. Проверка параметров
        try:
            validated_params = self._validate_parameters(parameters)
        except ValueError as e:
            validation_errors.append(str(e))
            validated_params = parameters  # использовать оригинальные параметры при ошибке валидации
        
        # 6. Проверка соответствия параметров
        param_placeholders = re.findall(r'\$(\w+)|:(\w+)|\{(\w+)\}', sql_query)
        flat_param_names = []
        for match in param_placeholders:
            # Получаем имя параметра из одного из трех возможных групп
            param_name = next((x for x in match if x), None)
            if param_name:
                flat_param_names.append(param_name)
        
        missing_params = set(flat_param_names) - set(parameters.keys())
        if missing_params:
            validation_errors.append(f"Отсутствующие параметры в запросе: {', '.join(missing_params)}")
        
        # 7. Оценка безопасности
        safety_score = self._calculate_safety_score(sql_query, validated_params if 'validated_params' in locals() else parameters)
        
        is_valid = len(validation_errors) == 0
        
        return ValidatedSQL(
            sql=sql_query if is_valid else "",  # Возвращаем пустую строку, если невалиден
            parameters=validated_params if 'validated_params' in locals() else parameters,
            is_valid=is_valid,
            validation_errors=validation_errors,
            safety_score=safety_score
        )
    
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
            if ident.upper() in {"SELECT", "FROM", "WHERE", "AND", "OR", "ORDER", "BY", "LIMIT", "OFFSET", "WITH", "AS", "ON", "INNER", "LEFT", "RIGHT", "JOIN", "GROUP", "HAVING"}:
                continue

            # Проверка формата идентификатора
            if not self.identifier_pattern.match(ident) and not self.schema_qualified_pattern.match(ident):
                raise ValueError(f"Некорректный идентификатор: '{ident}'")

    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация параметров на безопасность"""
        validated = {}
        for key, value in parameters.items():
            # Проверка имени параметра
            # Разрешаем имена вида '1', '2' (для PostgreSQL $1, $2) или 'p1', 'p2' или обычные имена
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$|^\d+$', key):
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

    async def restart(self) -> bool:
        """
        Перезапуск сервиса без полной перезагрузки системного контекста.
        
        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        try:
            # Сначала останавливаем текущий экземпляр
            await self.shutdown()
            
            # Затем инициализируем заново
            return await self.initialize()
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка перезапуска SQLValidatorService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        if self.event_bus_logger:
            await self.event_bus_logger.info("Завершение работы SQLValidatorService")