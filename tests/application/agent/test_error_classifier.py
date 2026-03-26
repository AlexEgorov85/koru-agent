"""
Тесты для ErrorClassifier.

Проверяет:
1. Классификацию TRANSIENT ошибок (сеть, таймауты)
2. Классификацию LOGIC ошибок (по умолчанию)
3. Классификацию VALIDATION ошибок (валидация)
4. Классификацию FATAL ошибок (критические)
5. Метод get_recommendation_for_type()
"""
import pytest

from core.agent.components.error_classifier import ErrorClassifier
from core.models.enums.common_enums import ErrorType


class TestErrorClassifier:
    """Тесты классификатора ошибок."""

    @pytest.fixture
    def classifier(self):
        """Создаёт классификатор ошибок."""
        return ErrorClassifier()

    # ==========================================================
    # TRANSIENT ошибки
    # ==========================================================

    def test_classify_timeout_error(self, classifier):
        """Тест: таймаут классифицируется как TRANSIENT."""
        error = TimeoutError("Connection timeout")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.TRANSIENT
        assert recommendation == "retry_with_backoff"

    def test_classify_connection_error(self, classifier):
        """Тест: ошибка соединения классифицируется как TRANSIENT."""
        error = ConnectionError("Connection refused")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.TRANSIENT
        assert recommendation == "retry_with_backoff"

    def test_classify_network_error(self, classifier):
        """Тест: сетевая ошибка классифицируется как TRANSIENT."""
        error = Exception("Network error: temporarily unavailable")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.TRANSIENT
        assert recommendation == "retry_with_backoff"

    def test_classify_rate_limit_error(self, classifier):
        """Тест: rate limit классифицируется как TRANSIENT."""
        error = Exception("Rate limit exceeded, throttled")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.TRANSIENT
        assert recommendation == "retry_with_backoff"

    # ==========================================================
    # VALIDATION ошибки
    # ==========================================================

    def test_classify_validation_error(self, classifier):
        """Тест: ошибка валидации классифицируется как VALIDATION."""
        error = ValueError("Validation failed: invalid input")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.VALIDATION
        assert recommendation == "abort_and_log"

    def test_classify_schema_error(self, classifier):
        """Тест: ошибка схемы классифицируется как VALIDATION."""
        error = Exception("Schema validation error: missing required field")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.VALIDATION
        assert recommendation == "abort_and_log"

    def test_classify_attribute_error(self, classifier):
        """Тест: AttributeError классифицируется как VALIDATION."""
        error = AttributeError("Object has no attribute 'name'")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.VALIDATION
        assert recommendation == "abort_and_log"

    def test_classify_key_error(self, classifier):
        """Тест: KeyError классифицируется как VALIDATION."""
        error = KeyError("Missing required key 'query'")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.VALIDATION
        assert recommendation == "abort_and_log"

    # ==========================================================
    # FATAL ошибки
    # ==========================================================

    def test_classify_fatal_error(self, classifier):
        """Тест: критическая ошибка классифицируется как FATAL."""
        error = RuntimeError("Fatal error: system corrupt")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.FATAL
        assert recommendation == "fail_immediately"

    def test_classify_critical_error(self, classifier):
        """Тест: critical ошибка классифицируется как FATAL."""
        error = Exception("Critical failure: unrecoverable state")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.FATAL
        assert recommendation == "fail_immediately"

    # ==========================================================
    # LOGIC ошибки (по умолчанию)
    # ==========================================================

    def test_classify_logic_error_default(self, classifier):
        """Тест: неизвестная ошибка классифицируется как LOGIC."""
        error = Exception("Some unknown error occurred")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.LOGIC
        assert recommendation == "switch_pattern"

    def test_classify_logic_error_no_keywords(self, classifier):
        """Тест: ошибка без ключевых слов классифицируется как LOGIC."""
        error = RuntimeError("Something went wrong")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.LOGIC
        assert recommendation == "switch_pattern"

    def test_classify_logic_error_unexpected_result(self, classifier):
        """Тест: ошибка неожиданного результата классифицируется как LOGIC."""
        error = Exception("Unexpected result format")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.LOGIC
        assert recommendation == "switch_pattern"

    # ==========================================================
    # Приоритет классификации
    # ==========================================================

    def test_fatal_has_highest_priority(self, classifier):
        """Тест: FATAL имеет наивысший приоритет."""
        # Ошибка содержит и "timeout" (TRANSIENT) и "fatal" (FATAL)
        error = Exception("Fatal timeout error")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.FATAL
        assert recommendation == "fail_immediately"

    def test_validation_has_higher_priority_than_transient(self, classifier):
        """Тест: VALIDATION имеет приоритет над TRANSIENT."""
        # Ошибка содержит и "connection" (TRANSIENT) и "invalid" (VALIDATION)
        error = Exception("Invalid connection: validation failed")
        error_type, recommendation = classifier.classify(error, "test.capability")

        assert error_type == ErrorType.VALIDATION
        assert recommendation == "abort_and_log"

    # ==========================================================
    # get_recommendation_for_type()
    # ==========================================================

    def test_get_recommendation_for_transient(self, classifier):
        """Тест: рекомендация для TRANSIENT."""
        recommendation = classifier.get_recommendation_for_type(ErrorType.TRANSIENT)
        assert recommendation == "retry_with_backoff"

    def test_get_recommendation_for_logic(self, classifier):
        """Тест: рекомендация для LOGIC."""
        recommendation = classifier.get_recommendation_for_type(ErrorType.LOGIC)
        assert recommendation == "switch_pattern"

    def test_get_recommendation_for_validation(self, classifier):
        """Тест: рекомендация для VALIDATION."""
        recommendation = classifier.get_recommendation_for_type(ErrorType.VALIDATION)
        assert recommendation == "abort_and_log"

    def test_get_recommendation_for_fatal(self, classifier):
        """Тест: рекомендация для FATAL."""
        recommendation = classifier.get_recommendation_for_type(ErrorType.FATAL)
        assert recommendation == "fail_immediately"

    # ==========================================================
    # Интеграционные тесты
    # ==========================================================

    def test_full_classification_workflow(self, classifier):
        """Тест: полный цикл классификации."""
        # Сценарий 1: временная ошибка
        error1 = TimeoutError("Connection timeout")
        error_type1, rec1 = classifier.classify(error1, "db.execute")
        assert error_type1 == ErrorType.TRANSIENT
        assert rec1 == "retry_with_backoff"
        assert classifier.get_recommendation_for_type(error_type1) == rec1

        # Сценарий 2: логическая ошибка
        error2 = Exception("Unexpected result format")
        error_type2, rec2 = classifier.classify(error2, "search.execute")
        assert error_type2 == ErrorType.LOGIC
        assert rec2 == "switch_pattern"
        assert classifier.get_recommendation_for_type(error_type2) == rec2

        # Сценарий 3: ошибка валидации
        error3 = ValueError("Invalid parameter: query is required")
        error_type3, rec3 = classifier.classify(error3, "api.call")
        assert error_type3 == ErrorType.VALIDATION
        assert rec3 == "abort_and_log"
        assert classifier.get_recommendation_for_type(error_type3) == rec3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
