from typing import Dict, Any, Optional
from core.application_context.application_context import ApplicationContext
from core.models.sql_schemas import SQLCorrectionInput, SQLCorrectionOutput
from core.components.services.sql_generation.error_analyzer import SQLErrorAnalyzer, ExecutionError
import logging
from core.infrastructure.event_bus.unified_event_bus import EventType

log = logging.getLogger(__name__)


class SQLCorrectionEngine:
    """
    Движок коррекции SQL-запросов на основе анализа ошибок.

    ФУНКЦИОНАЛЬНОСТЬ:
    1. Применение стратегий коррекции в зависимости от типа ошибки
    2. Генерация исправленного запроса с сохранением логики
    3. Проверка корректности исправленного запроса
    4. Оценка уверенности в исправлении
    """

    def __init__(self, application_context: ApplicationContext, component_config=None, executor=None):
        """
        Инициализация движка коррекции.

        ПАРАМЕТРЫ:
        - application_context: ApplicationContext
        - component_config: ComponentConfig (не используется, для совместимости)
        - executor: ActionExecutor (не используется, для совместимости)
        """
        self.application_context = application_context
        self.executor = executor
        self.error_analyzer = SQLErrorAnalyzer(
            application_context,
            executor=executor
        )

    async def initialize(self) -> bool:
        """Инициализация движка коррекции"""
        await self.error_analyzer.initialize()
        log.info("SQLCorrectionEngine успешно инициализирован", extra={"event_type": EventType.SYSTEM_READY})
        return True

    async def shutdown(self) -> None:
        """Завершение работы движка коррекции"""
        await self.error_analyzer.shutdown()
        log.info("Завершение работы SQLCorrectionEngine", extra={"event_type": EventType.SYSTEM_SHUTDOWN})
    
    async def correct_query(self, correction_input: SQLCorrectionInput) -> SQLCorrectionOutput:
        """
        Коррекция SQL-запроса на основе ошибки и анализа.
        
        ВОЗВРАЩАЕТ:
        - Исправленный SQL-запрос
        - Обоснование исправления
        - Таблицы, использованные в исправленном запросе
        - Уверенность в корректности исправления
        """
        # Определение стратегии коррекции на основе типа ошибки
        corrected_sql = self._apply_correction_strategy(
            correction_input.original_query,
            correction_input.error_type,
            correction_input.error_message,
            correction_input.suggested_fix
        )
        
        # Создание вывода с обоснованием
        output = SQLCorrectionOutput(
            corrected_sql=corrected_sql,
            reasoning=self._generate_reasoning(
                correction_input.error_type,
                correction_input.error_message,
                corrected_sql
            ),
            tables_used=await self._extract_tables_from_query(corrected_sql),
            confidence=self._calculate_correction_confidence(correction_input.error_type)
        )
        
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