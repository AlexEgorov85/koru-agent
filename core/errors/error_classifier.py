"""
Классификатор ошибок для принятия решений о паттернах поведения.

АРХИТЕКТУРА:
- Классифицирует ошибки по типам (TRANSIENT, LOGIC, VALIDATION, FATAL)
- Возвращает рекомендацию для обработки ошибки
- Используется в SafeExecutor перед записью в FailureMemory

ОТВЕТСТВЕННОСТЬ:
- Анализ текста ошибки
- Определение типа ошибки
- Возврат рекомендации (retry, switch, abort, fail)
"""
from typing import Tuple
from core.models.enums.common_enums import ErrorType


class ErrorClassifier:
    """
    Классификатор ошибок для правильных решений.
    
    ПРИНЦИПЫ:
    - Классификация на основе ключевых слов в тексте ошибки
    - Приоритет: FATAL > VALIDATION > TRANSIENT > LOGIC
    - Рекомендации соответствуют типу ошибки
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    classifier = ErrorClassifier()
    error_type, recommendation = classifier.classify(
        TimeoutError("Connection timeout"),
        "search_database.execute"
    )
    # → ErrorType.TRANSIENT, "retry_with_backoff"
    """
    
    # Ключевые слова для классификации ошибок
    TRANSIENT_KEYWORDS = [
        'timeout', 'connection', 'network', 'temporarily',
        'unavailable', 'refused', 'reset', 'aborted',
        'rate limit', 'throttled', 'busy', 'overloaded'
    ]
    
    VALIDATION_KEYWORDS = [
        'validation', 'invalid', 'required', 'schema',
        'malformed', 'incorrect', 'missing',
        'type error', 'attributeerror', 'keyerror',
        'attribute error', 'key error'
    ]
    
    FATAL_KEYWORDS = [
        'fatal', 'critical', 'unrecoverable', 'corrupt',
        'irrecoverable', 'terminal', 'catastrophic'
    ]
    
    def classify(self, error: Exception, capability: str) -> Tuple[ErrorType, str]:
        """
        Классифицировать ошибку и вернуть рекомендацию.
        
        ПАРАМЕТРЫ:
        - error: исключение для классификации
        - capability: имя capability где произошла ошибка
        
        ВОЗВРАЩАЕТ:
        - Tuple[ErrorType, str]: (тип_ошибки, рекомендация)
        
        АЛГОРИТМ:
        1. Проверка на FATAL ошибки (критические)
        2. Проверка на VALIDATION ошибки (валидация)
        3. Проверка на TRANSIENT ошибки (временные)
        4. По умолчанию — LOGIC ошибка (логическая)
        """
        error_msg = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Объединяем сообщение ошибки с типом исключения
        full_text = f"{error_msg} {error_type_name}"
        
        # FATAL — критические ошибки (приоритет 1)
        if self._has_keywords(full_text, self.FATAL_KEYWORDS):
            return ErrorType.FATAL, "fail_immediately"
        
        # VALIDATION — ошибки валидации (приоритет 2)
        if self._has_keywords(full_text, self.VALIDATION_KEYWORDS):
            return ErrorType.VALIDATION, "abort_and_log"
        
        # TRANSIENT — временные ошибки (приоритет 3)
        if self._has_keywords(full_text, self.TRANSIENT_KEYWORDS):
            return ErrorType.TRANSIENT, "retry_with_backoff"
        
        # LOGIC — логические ошибки по умолчанию (приоритет 4)
        return ErrorType.LOGIC, "switch_pattern"
    
    def _has_keywords(self, text: str, keywords: list) -> bool:
        """
        Проверить наличие ключевых слов в тексте.
        
        ПАРАМЕТРЫ:
        - text: текст для проверки
        - keywords: список ключевых слов
        
        ВОЗВРАЩАЕТ:
        - bool: True если найдено хотя бы одно ключевое слово
        """
        return any(keyword in text for keyword in keywords)
    
    def get_recommendation_for_type(self, error_type: ErrorType) -> str:
        """
        Получить рекомендацию для типа ошибки.
        
        ПАРАМЕТРЫ:
        - error_type: тип ошибки
        
        ВОЗВРАЩАЕТ:
        - str: рекомендация по обработке
        
        ТАБЛИЦА СООТВЕТСТВИЯ:
        - TRANSIENT → "retry_with_backoff"
        - LOGIC → "switch_pattern"
        - VALIDATION → "abort_and_log"
        - FATAL → "fail_immediately"
        """
        recommendations = {
            ErrorType.TRANSIENT: "retry_with_backoff",
            ErrorType.LOGIC: "switch_pattern",
            ErrorType.VALIDATION: "abort_and_log",
            ErrorType.FATAL: "fail_immediately"
        }
        return recommendations.get(error_type, "switch_pattern")
