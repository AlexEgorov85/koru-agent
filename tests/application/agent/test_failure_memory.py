"""
Тесты для FailureMemory.

Проверяет:
1. Запись ошибок (record)
2. Сброс ошибок при успехе (reset)
3. Проверку необходимости переключения паттерна (should_switch_pattern)
4. Подсчёт ошибок (get_count)
5. Получение рекомендаций (get_recommendation)
6. Временную очистку записей (TTL)
7. Получение последних ошибок (get_recent_errors)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from core.agent.components.failure_memory import FailureMemory, FailureRecord
from core.models.enums.common_enums import ErrorType


class TestFailureRecord:
    """Тесты записи об ошибке."""

    def test_create_failure_record(self):
        """Тест: создание записи об ошибке."""
        timestamp = datetime.now()
        record = FailureRecord(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=timestamp
        )

        assert record.capability == "test.capability"
        assert record.error_type == ErrorType.TRANSIENT
        assert record.count == 1
        assert record.consecutive == 1
        assert record.last_attempt == timestamp

    def test_increment_same_type(self):
        """Тест: увеличение счётчика для того же типа ошибки."""
        timestamp = datetime.now()
        record = FailureRecord(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=timestamp
        )

        # Увеличиваем счётчик
        new_timestamp = timestamp + timedelta(minutes=1)
        record.increment(new_timestamp, same_type=True)

        assert record.count == 2
        assert record.consecutive == 2
        assert record.last_attempt == new_timestamp

    def test_increment_different_type(self):
        """Тест: сброс consecutive при другом типе ошибки."""
        timestamp = datetime.now()
        record = FailureRecord(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=timestamp
        )

        # Увеличиваем счётчик с другим типом
        new_timestamp = timestamp + timedelta(minutes=1)
        record.increment(new_timestamp, same_type=False)

        assert record.count == 2
        assert record.consecutive == 1  # Сброшено
        assert record.last_attempt == new_timestamp

    def test_to_dict(self):
        """Тест: конвертация в словарь."""
        timestamp = datetime.now()
        record = FailureRecord(
            capability="test.capability",
            error_type=ErrorType.VALIDATION,
            timestamp=timestamp
        )

        result = record.to_dict()

        assert result["capability"] == "test.capability"
        assert result["error_type"] == "validation"
        assert result["count"] == 1
        assert result["consecutive"] == 1
        assert "last_attempt" in result


class TestFailureMemory:
    """Тесты памяти ошибок."""

    @pytest.fixture
    def failure_memory(self):
        """Создаёт FailureMemory с коротким TTL для тестов."""
        return FailureMemory(max_age_minutes=30)

    # ==========================================================
    # record() — запись ошибок
    # ==========================================================

    def test_record_first_error(self, failure_memory):
        """Тест: запись первой ошибки."""
        timestamp = datetime.now()
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=timestamp
        )

        assert len(failure_memory) == 1
        assert failure_memory.get_count("test.capability") == 1

    def test_record_same_error_multiple_times(self, failure_memory):
        """Тест: запись одной и той же ошибки несколько раз."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=2)
        )

        assert len(failure_memory) == 1  # Одна запись
        assert failure_memory.get_count("test.capability") == 3

    def test_record_different_error_types(self, failure_memory):
        """Тест: запись разных типов ошибок для одной capability."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )

        assert len(failure_memory) == 2  # Две записи (разные типы)
        assert failure_memory.get_count("test.capability") == 2

    # ==========================================================
    # reset() — сброс ошибок
    # ==========================================================

    def test_reset_clears_all_errors_for_capability(self, failure_memory):
        """Тест: сброс удаляет все ошибки для capability."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )

        assert len(failure_memory) == 2

        failure_memory.reset("test.capability")

        assert len(failure_memory) == 0
        assert failure_memory.get_count("test.capability") == 0

    def test_reset_does_not_affect_other_capabilities(self, failure_memory):
        """Тест: сброс не влияет на другие capability."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="capability.one",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="capability.two",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )

        failure_memory.reset("capability.one")

        assert len(failure_memory) == 1
        assert failure_memory.get_count("capability.two") == 1

    # ==========================================================
    # should_switch_pattern() — проверка переключения
    # ==========================================================

    def test_should_switch_on_consecutive_logic_errors(self, failure_memory):
        """Тест: переключение при 3 последовательных LOGIC ошибках."""
        base_time = datetime.now()
        
        # 3 последовательные LOGIC ошибки
        for i in range(3):
            failure_memory.record(
                capability="test.capability",
                error_type=ErrorType.LOGIC,
                timestamp=base_time + timedelta(minutes=i)
            )

        assert failure_memory.should_switch_pattern("test.capability") is True

    def test_should_switch_on_two_logic_errors(self):
        """Тест: переключение при 2 LOGIC ошибках (TOTAL_ERRORS_THRESHOLD=2)."""
        failure_memory = FailureMemory(max_age_minutes=30)
        base_time = datetime.now()

        # 2 последовательные LOGIC ошибки
        for i in range(2):
            failure_memory.record(
                capability="test.capability",
                error_type=ErrorType.LOGIC,
                timestamp=base_time + timedelta(minutes=i)
            )

        # 2 ошибки превышают TOTAL_ERRORS_THRESHOLD
        assert failure_memory.should_switch_pattern("test.capability") is True

    def test_should_not_switch_on_single_logic_error(self, failure_memory):
        """Тест: нет переключения при 1 LOGIC ошибке."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=datetime.now()
        )

        assert failure_memory.should_switch_pattern("test.capability") is False

    def test_should_switch_on_total_errors_threshold(self, failure_memory):
        """Тест: переключение при 2 ошибках любого типа."""
        base_time = datetime.now()
        
        # 2 ошибки разных типов
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.VALIDATION,
            timestamp=base_time + timedelta(minutes=1)
        )

        assert failure_memory.should_switch_pattern("test.capability") is True

    def test_should_switch_when_no_capability(self, failure_memory):
        """Тест: нет переключения если нет ошибок."""
        assert failure_memory.should_switch_pattern("nonexistent.capability") is False

    # ==========================================================
    # get_count() — подсчёт ошибок
    # ==========================================================

    def test_get_count_total(self, failure_memory):
        """Тест: получение общего количества ошибок."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time + timedelta(minutes=2)
        )

        assert failure_memory.get_count("test.capability") == 3

    def test_get_count_by_error_type(self, failure_memory):
        """Тест: получение количества ошибок по типу."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )

        assert failure_memory.get_count("test.capability", ErrorType.TRANSIENT) == 1
        assert failure_memory.get_count("test.capability", ErrorType.LOGIC) == 1

    # ==========================================================
    # get_recommendation() — получение рекомендаций
    # ==========================================================

    def test_get_recommendation_transient(self, failure_memory):
        """Тест: рекомендация для TRANSIENT."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=datetime.now()
        )

        recommendation = failure_memory.get_recommendation("test.capability")
        assert recommendation == "retry_with_backoff"

    def test_get_recommendation_logic(self, failure_memory):
        """Тест: рекомендация для LOGIC."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=datetime.now()
        )

        recommendation = failure_memory.get_recommendation("test.capability")
        assert recommendation == "switch_pattern"

    def test_get_recommendation_validation(self, failure_memory):
        """Тест: рекомендация для VALIDATION."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.VALIDATION,
            timestamp=datetime.now()
        )

        recommendation = failure_memory.get_recommendation("test.capability")
        assert recommendation == "abort_and_log"

    def test_get_recommendation_fatal(self, failure_memory):
        """Тест: рекомендация для FATAL."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.FATAL,
            timestamp=datetime.now()
        )

        recommendation = failure_memory.get_recommendation("test.capability")
        assert recommendation == "fail_immediately"

    def test_get_recommendation_no_errors(self, failure_memory):
        """Тест: нет рекомендации если нет ошибок."""
        recommendation = failure_memory.get_recommendation("nonexistent.capability")
        assert recommendation is None

    # ==========================================================
    # get_recent_errors() — последние ошибки
    # ==========================================================

    def test_get_recent_errors(self, failure_memory):
        """Тест: получение последних ошибок."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.VALIDATION,
            timestamp=base_time + timedelta(minutes=2)
        )

        recent = failure_memory.get_recent_errors("test.capability", limit=2)

        assert len(recent) == 2
        # Последние первыми
        assert recent[0].error_type == ErrorType.VALIDATION
        assert recent[1].error_type == ErrorType.LOGIC

    # ==========================================================
    # TTL очистка
    # ==========================================================

    def test_ttl_cleanup_expired_records(self):
        """Тест: TTL очистка удаляет старые записи."""
        # Создаём FailureMemory с TTL 1 минута
        failure_memory = FailureMemory(max_age_minutes=1)
        
        old_time = datetime.now() - timedelta(minutes=5)
        new_time = datetime.now()
        
        # Записываем старую ошибку
        failure_memory.record(
            capability="old.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=old_time
        )
        # Записываем новую ошибку
        failure_memory.record(
            capability="new.capability",
            error_type=ErrorType.LOGIC,
            timestamp=new_time
        )

        # Принудительно вызываем очистку
        failure_memory._cleanup()

        assert len(failure_memory) == 1
        assert failure_memory.get_count("new.capability") == 1
        assert failure_memory.get_count("old.capability") == 0

    # ==========================================================
    # clear() и __repr__()
    # ==========================================================

    def test_clear_all_errors(self, failure_memory):
        """Тест: полная очистка всех ошибок."""
        base_time = datetime.now()
        
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.LOGIC,
            timestamp=base_time + timedelta(minutes=1)
        )

        assert len(failure_memory) == 2

        failure_memory.clear()

        assert len(failure_memory) == 0

    def test_repr(self, failure_memory):
        """Тест: строковое представление."""
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=datetime.now()
        )

        repr_str = repr(failure_memory)
        assert "FailureMemory" in repr_str
        assert "failures=1" in repr_str

    # ==========================================================
    # Интеграционные тесты
    # ==========================================================

    def test_full_workflow(self, failure_memory):
        """Тест: полный цикл работы с FailureMemory."""
        base_time = datetime.now()

        # Сценарий: серия ошибок при выполнении capability
        capability = "search.database"

        # Ошибка 1: временная
        failure_memory.record(
            capability=capability,
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time
        )
        assert failure_memory.get_recommendation(capability) == "retry_with_backoff"
        assert failure_memory.should_switch_pattern(capability) is False

        # Ошибка 2: ещё одна временная (после retry)
        failure_memory.record(
            capability=capability,
            error_type=ErrorType.TRANSIENT,
            timestamp=base_time + timedelta(minutes=1)
        )
        # 2 ошибки → переключение паттерна
        assert failure_memory.should_switch_pattern(capability) is True
        # Рекомендация всё ещё retry_with_backoff (первая запись)
        assert failure_memory.get_recommendation(capability) == "retry_with_backoff"

        # Успех после переключения паттерна — сброс
        failure_memory.reset(capability)
        assert failure_memory.get_count(capability) == 0
        assert failure_memory.should_switch_pattern(capability) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
