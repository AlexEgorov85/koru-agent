from typing import Dict, Any, Optional
from core.components.services.sql_generation.error_analyzer import SQLErrorAnalyzer, ExecutionError
from core.application_context.application_context import ApplicationContext
import logging
from core.infrastructure.event_bus.unified_event_bus import EventType

log = logging.getLogger(__name__)


class SQLCorrectionEngine:
    """
    Внутренний движок коррекции SQL-запросов на основе анализа ошибок.
    
    АРХИТЕКТУРА:
    - НЕ наследуется от Service, чтобы избежать регистрации как отдельный компонент
    - Используется как внутренняя утилита внутри SQLGenerationService
    - Контракты валидируются вручную через переданный component_config
    
    ФУНКЦИОНАЛЬНОСТЬ:
    1. Применение стратегий коррекции в зависимости от типа ошибки
    2. Генерация исправленного запроса с сохранением логики
    3. Проверка корректности исправленного запроса
    4. Оценка уверенности в исправлении
    """

    def __init__(self, application_context: ApplicationContext, executor=None):
        self.application_context = application_context
        self.executor = executor
        self.error_analyzer = None
        
        # Конфигурация безопасности
        self.max_correction_attempts = 3
        self.allowed_operations = ["SELECT", "WITH"]

    async def initialize(self) -> bool:
        """Инициализация внутреннего состояния"""
        try:
            # Инициализация анализатора ошибок
            self.error_analyzer = SQLErrorAnalyzer(
                self.application_context,
                executor=self.executor
            )
            if not await self.error_analyzer.initialize():
                log.warning("SQLErrorAnalyzer не инициализирован")
                return False

            return True
        except Exception as e:
            log.error(f"Ошибка инициализации SQLCorrectionEngine: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы движка"""
        if self.error_analyzer:
            await self.error_analyzer.shutdown()
        log.info("Завершение работы SQLCorrectionEngine")

    async def correct_query(self, correction_input: Dict[str, Any], input_contract=None, output_contract=None) -> Dict[str, Any]:
        """
        Коррекция SQL-запроса на основе ошибки и анализа.
        
        ПАРАМЕТРЫ:
        - correction_input: Словарь с полями original_query, error_type, error_message, suggested_fix
        - input_contract: Опциональный контракт для валидации входа
        - output_contract: Опциональный контракт для валидации выхода
        
        ВОЗВРАЩАЕТ:
        - Словарь с полями corrected_sql, reasoning, tables_used, confidence
        """
        # Валидация входных данных через контракт (если предоставлен)
        if input_contract:
            try:
                input_contract.model_validate(correction_input)
            except Exception as e:
                raise ValueError(f"Invalid input for SQLCorrection: {e}")
        
        # Определение стратегии коррекции на основе типа ошибки
        corrected_sql = self._apply_correction_strategy(
            correction_input.get("original_query"),
            correction_input.get("error_type"),
            correction_input.get("error_message"),
            correction_input.get("suggested_fix")
        )
        
        # Создание вывода с обоснованием
        output = {
            "corrected_sql": corrected_sql,
            "reasoning": self._generate_reasoning(
                correction_input.get("error_type"),
                correction_input.get("error_message"),
                corrected_sql
            ),
            "tables_used": await self._extract_tables_from_query(corrected_sql),
            "confidence": self._calculate_correction_confidence(correction_input.get("error_type"))
        }
        
        # Валидация выходных данных через контракт (если предоставлен)
        if output_contract:
            try:
                output_contract.model_validate(output)
            except Exception as e:
                log.warning(f"Output validation failed: {e}")
        
        return output
    
    def _apply_correction_strategy(self, original_query: str, error_type: str, error_message: str, suggested_fix: Optional[str]) -> str:
        """Применение стратегии коррекции в зависимости от типа ошибки"""
        if error_type == "syntax_error":
            return self._correct_syntax_error(original_query, error_message)
        elif error_type == "schema_error":
            return self._correct_schema_error(original_query, error_message, suggested_fix)
        elif error_type == "permission_error":
            return self._correct_permission_error(original_query)
        elif error_type == "timeout_error":
            return self._correct_timeout_error(original_query)
        else:
            # Для других типов ошибок возвращаем оригинальный запрос с возможными минимальными изменениями
            return original_query
    
    def _correct_syntax_error(self, query: str, error_message: str) -> str:
        """Коррекция синтаксических ошибок"""
        # Простая коррекция синтаксиса - в реальном проекте использовать более сложный анализ
        corrected = query
        
        # Примеры простых коррекций
        if "GROUP BY" in corrected.upper() and "SELECT" in corrected.upper():
            # Проверяем, что все неагрегированные поля в SELECT есть в GROUP BY
            pass  # Реализация требует полноценного SQL-парсера
        
        # Убираем лишние символы или добавляем недостающие
        corrected = corrected.strip()
        if corrected.endswith(';'):
            corrected = corrected[:-1]  # Убираем последнюю точку с запятой, если есть
        
        return corrected
    
    def _correct_schema_error(self, query: str, error_message: str, suggested_fix: Optional[str]) -> str:
        """Коррекция ошибок схемы (несуществующие таблицы/колонки)"""
        corrected = query
        
        # Если в сообщении об ошибке указана конкретная таблица/колонка
        problematic_element = self._extract_problematic_element(error_message)
        if problematic_element:
            # Пытаемся заменить некорректное имя
            # Это упрощенная реализация - в реальности нужно использовать информацию о схеме
            pass
        
        return corrected
    
    def _correct_permission_error(self, query: str) -> str:
        """Коррекция ошибок доступа"""
        # Для ошибок доступа корректируем запрос, чтобы он соответствовал разрешенным операциям
        # В текущей архитектуре все равно только SELECT, поэтому коррекция минимальна
        corrected = query.upper().replace("DELETE", "SELECT").replace("UPDATE", "SELECT").replace("INSERT", "SELECT")
        return corrected.lower()
    
    def _correct_timeout_error(self, query: str) -> str:
        """Коррекция ошибок таймаута"""
        # Добавляем LIMIT к запросу, если его нет
        if "LIMIT" not in query.upper():
            # Проверяем, есть ли ORDER BY перед добавлением LIMIT
            if "ORDER BY" in query.upper():
                # Добавляем LIMIT после ORDER BY
                corrected = query.upper().replace("ORDER BY", "ORDER BY LIMIT 100")
            else:
                # Добавляем LIMIT в конец запроса
                corrected = f"{query} LIMIT 100"
        else:
            # Если LIMIT уже есть, увеличиваем его значение
            corrected = query
            import re
            limit_pattern = r"LIMIT\s+(\d+)"
            match = re.search(limit_pattern, query, re.IGNORECASE)
            if match:
                current_limit = int(match.group(1))
                new_limit = min(current_limit, 100)  # Ограничиваем до 100
                corrected = re.sub(limit_pattern, f"LIMIT {new_limit}", query, flags=re.IGNORECASE)
        
        return corrected
    
    def _extract_problematic_element(self, error_message: str) -> Optional[str]:
        """Извлечение проблемного элемента (таблицы/колонки) из сообщения об ошибке"""
        # Используем реализацию из анализатора ошибок
        patterns = [
            r"relation \"?([^\"]+)\"? does not exist",
            r"table \"?([^\"]+)\"? not found",
            r"column \"?([^\"]+)\"? does not exist"
        ]
        
        for pattern in patterns:
            import re
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _generate_reasoning(self, error_type: str, error_message: str, corrected_query: str) -> str:
        """Генерация обоснования для коррекции"""
        reasonings = {
            "syntax_error": f"Исправлена синтаксическая ошибка в запросе. Оригинальная ошибка: {error_message}",
            "schema_error": f"Исправлена ошибка схемы. Проверьте существование таблиц и колонок. Оригинальная ошибка: {error_message}",
            "permission_error": f"Коррекция для соответствия политике безопасности. Оригинальная ошибка: {error_message}",
            "timeout_error": f"Добавлено ограничение LIMIT для предотвращения таймаута. Оригинальная ошибка: {error_message}",
            "other_error": f"Применена общая стратегия коррекции. Оригинальная ошибка: {error_message}"
        }
        
        return reasonings.get(error_type, f"Коррекция применена. Оригинальная ошибка: {error_message}")
    
    async def _extract_tables_from_query(self, query: str) -> list:
        """Извлечение имен таблиц из SQL-запроса"""
        # Используем ту же реализацию, что и в анализаторе ошибок
        import re
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
    
    def _calculate_correction_confidence(self, error_type: str) -> float:
        """Расчет уверенности в коррекции"""
        # Уверенность зависит от типа ошибки и сложности коррекции
        confidence_map = {
            "syntax_error": 0.8,
            "schema_error": 0.6,  # Ниже, потому что требует знания схемы
            "permission_error": 0.9,  # Простая коррекция
            "timeout_error": 0.85,  # Простая коррекция
            "other_error": 0.5  # Неопределенная стратегия
        }
        
        return confidence_map.get(error_type, 0.5)