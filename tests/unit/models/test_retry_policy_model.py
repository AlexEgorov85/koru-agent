"""
Тесты для модели RetryPolicy (ErrorCategory, ExecutionErrorInfo, RetryDecision, RetryResult).
"""
import pytest
from models.retry_policy import ErrorCategory, ExecutionErrorInfo, RetryDecision, RetryResult


def test_error_category_enum_values():
    """Тест значений ErrorCategory."""
    assert ErrorCategory.TRANSIENT.value == "transient"
    assert ErrorCategory.INVALID_INPUT.value == "invalid_input"
    assert ErrorCategory.TOOL_FAILURE.value == "tool_failure"
    assert ErrorCategory.FATAL.value == "fatal"
    
    # Проверяем все значения
    all_categories = [category.value for category in ErrorCategory]
    expected_categories = ["transient", "invalid_input", "tool_failure", "fatal"]
    assert set(all_categories) == set(expected_categories)


def test_execution_error_info_dataclass():
    """Тест ExecutionErrorInfo dataclass."""
    # Тест создания
    error_info = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Тестовая ошибка",
        raw_error=Exception("Тестовое исключение")
    )
    
    assert error_info.category == ErrorCategory.TRANSIENT
    assert error_info.message == "Тестовая ошибка"
    assert isinstance(error_info.raw_error, Exception)
    assert str(error_info.raw_error) == "Тестовое исключение"


def test_execution_error_info_optional_raw_error():
    """Тест ExecutionErrorInfo с опциональным raw_error."""
    error_info = ExecutionErrorInfo(
        category=ErrorCategory.FATAL,
        message="Ошибка без исключения"
        # raw_error не указан, будет None
    )
    
    assert error_info.category == ErrorCategory.FATAL
    assert error_info.message == "Ошибка без исключения"
    assert error_info.raw_error is None


def test_retry_decision_enum_values():
    """Тест значений RetryDecision."""
    assert RetryDecision.RETRY.value == "retry"
    assert RetryDecision.ABORT.value == "abort"
    assert RetryDecision.FAIL.value == "fail"
    
    # Проверяем все значения
    all_decisions = [decision.value for decision in RetryDecision]
    expected_decisions = ["retry", "abort", "fail"]
    assert set(all_decisions) == set(expected_decisions)


def test_retry_result_dataclass():
    """Тест RetryResult dataclass."""
    # Тест создания
    result = RetryResult(
        decision=RetryDecision.RETRY,
        delay_seconds=2.5,
        reason="Временная сетевая ошибка"
    )
    
    assert result.decision == RetryDecision.RETRY
    assert result.delay_seconds == 2.5
    assert result.reason == "Временная сетевая ошибка"


def test_retry_result_default_values():
    """Тест значений по умолчанию для RetryResult."""
    result = RetryResult(decision=RetryDecision.FAIL)
    
    assert result.decision == RetryDecision.FAIL
    assert result.delay_seconds == 0.0  # значение по умолчанию
    assert result.reason is None        # значение по умолчанию


def test_error_info_and_retry_integration():
    """Тест интеграции ErrorCategory, ExecutionErrorInfo и RetryDecision."""
    # Создаем информацию об ошибке
    error_info = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Таймаут соединения",
        raw_error=TimeoutError("Connection timed out")
    )
    
    # В зависимости от категории ошибки принимаем решение
    if error_info.category == ErrorCategory.TRANSIENT:
        retry_result = RetryResult(
            decision=RetryDecision.RETRY,
            delay_seconds=1.0,
            reason="Временная ошибка, можно повторить"
        )
    elif error_info.category == ErrorCategory.FATAL:
        retry_result = RetryResult(
            decision=RetryDecision.FAIL,
            reason="Критическая ошибка, выполнение невозможно"
        )
    else:
        retry_result = RetryResult(
            decision=RetryDecision.ABORT,
            reason="Ошибка, которую нельзя исправить повтором"
        )
    
    # Проверяем, что решение соответствует ожиданиям
    assert retry_result.decision == RetryDecision.RETRY
    assert retry_result.reason == "Временная ошибка, можно повторить"
    assert retry_result.delay_seconds == 1.0