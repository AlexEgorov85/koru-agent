"""
Тесты для модели RetryAndErrorPolicy (RetryPolicy, ErrorCategory, ExecutionErrorInfo).
"""
import pytest
from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.retry_policy import ErrorCategory, ExecutionErrorInfo, RetryDecision, RetryResult


class TestRetryPolicyModel:
    """Тесты для модели RetryPolicy."""
    
    def test_retry_policy_creation(self):
        """Тест создания RetryPolicy."""
        policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0,
            jitter=True
        )
        
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.backoff_factor == 2.0
        assert policy.jitter is True
    
    def test_retry_policy_with_optional_fields(self):
        """Тест создания RetryPolicy с опциональными полями."""
        policy = RetryPolicy(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff_factor=1.5,
            jitter=False,
            retry_on_exceptions=[Exception, ValueError],
            retry_on_status_codes=[500, 502, 503]
        )
        
        assert policy.retry_on_exceptions == [Exception, ValueError]
        assert policy.retry_on_status_codes == [500, 502, 503]
    
    def test_retry_policy_default_values(self):
        """Тест значений по умолчанию для RetryPolicy."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3              # значение по умолчанию
        assert policy.base_delay == 1.0            # значение по умолчанию
        assert policy.max_delay == 60.0            # значение по умолчанию
        assert policy.backoff_factor == 2.0         # значение по умолчанию
        assert policy.jitter is True               # значение по умолчанию
        assert policy.retry_on_exceptions == []      # значение по умолчанию
        assert policy.retry_on_status_codes == []    # значение по умолчанию
    
    def test_retry_policy_equality(self):
        """Тест равенства RetryPolicy."""
        policy1 = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0
        )
        
        policy2 = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0
        )
        
        policy3 = RetryPolicy(
            max_retries=5,  # другое значение
            base_delay=1.0,
            max_delay=60.0
        )
        
        assert policy1 == policy2  # одинаковые по значению
        assert policy1 != policy3  # разные max_retries
        assert policy2 != policy3  # разные max_retries
    
    def test_retry_policy_serialization(self):
        """Тест сериализации RetryPolicy."""
        policy = RetryPolicy(
            max_retries=4,
            base_delay=2.0,
            max_delay=120.0,
            backoff_factor=3.0,
            jitter=False
        )
        
        data = policy.model_dump()
        
        assert data["max_retries"] == 4
        assert data["base_delay"] == 2.0
        assert data["max_delay"] == 120.0
        assert data["backoff_factor"] == 3.0
        assert data["jitter"] is False
    
    def test_retry_policy_from_dict(self):
        """Тест создания RetryPolicy из словаря."""
        data = {
            "max_retries": 6,
            "base_delay": 0.8,
            "max_delay": 90.0,
            "backoff_factor": 2.5,
            "jitter": True
        }
        
        policy = RetryPolicy.model_validate(data)
        
        assert policy.max_retries == 6
        assert policy.base_delay == 0.8
        assert policy.max_delay == 90.0
        assert policy.backoff_factor == 2.5
        assert policy.jitter is True


class TestErrorCategory:
    """Тесты для ErrorCategory."""
    
    def test_error_category_values(self):
        """Тест значений ErrorCategory."""
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.PERMANENT.value == "permanent"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.AUTHORIZATION.value == "authorization"
        assert ErrorCategory.RESOURCE_EXHAUSTED.value == "resource_exhausted"
        assert ErrorCategory.INTERNAL.value == "internal"
        assert ErrorCategory.UNAVAILABLE.value == "unavailable"
        assert ErrorCategory.BACKOFF.value == "backoff"
    
    def test_error_category_all_values(self):
        """Тест всех значений ErrorCategory."""
        all_categories = [category.value for category in ErrorCategory]
        expected_categories = [
            "transient", "permanent", "rate_limit", "network", 
            "timeout", "validation", "authentication", "authorization", 
            "resource_exhausted", "internal", "unavailable", "backoff"
        ]
        assert set(all_categories) == set(expected_categories)


class TestRetryDecision:
    """Тесты для RetryDecision."""
    
    def test_retry_decision_creation(self):
        """Тест создания RetryDecision."""
        decision = RetryDecision(
            decision="retry",
            delay_seconds=2.5,
            reason="Тестовое решение о повторной попытке"
        )
        
        assert decision.decision == "retry"
        assert decision.delay_seconds == 2.5
        assert decision.reason == "Тестовое решение о повторной попытке"
    
    def test_retry_decision_with_optional_fields(self):
        """Тест создания RetryDecision с опциональными полями."""
        decision = RetryDecision(
            decision="fail",
            delay_seconds=0.0,
            reason="Тестовое решение об отказе",
            metadata={"error_code": 500, "attempts_made": 3}
        )
        
        assert decision.metadata == {"error_code": 500, "attempts_made": 3}
    
    def test_retry_decision_default_values(self):
        """Тест значений по умолчанию для RetryDecision."""
        decision = RetryDecision(
            decision="retry",
            delay_seconds=1.0,
            reason="Тестовое решение"
        )
        
        assert decision.metadata == {}  # значение по умолчанию
    
    def test_retry_decision_equality(self):
        """Тест равенства RetryDecision."""
        decision1 = RetryDecision(
            decision="retry",
            delay_seconds=1.0,
            reason="Тест"
        )
        
        decision2 = RetryDecision(
            decision="retry",
            delay_seconds=1.0,
            reason="Тест"
        )
        
        decision3 = RetryDecision(
            decision="fail",  # другое решение
            delay_seconds=1.0,
            reason="Тест"
        )
        
        assert decision1 == decision2  # одинаковые по значению
        assert decision1 != decision3  # разные decision
        assert decision2 != decision3  # разные decision
    
    def test_retry_decision_serialization(self):
        """Тест сериализации RetryDecision."""
        decision = RetryDecision(
            decision="retry",
            delay_seconds=3.5,
            reason="Сериализация решения",
            metadata={"retry_count": 2, "next_attempt_after": "2023-01-01T00:00:00Z"}
        )
        
        data = decision.model_dump()
        
        assert data["decision"] == "retry"
        assert data["delay_seconds"] == 3.5
        assert data["reason"] == "Сериализация решения"
        assert data["metadata"] == {"retry_count": 2, "next_attempt_after": "2023-01-01T00:00:00Z"}
    
    def test_retry_decision_from_dict(self):
        """Тест создания RetryDecision из словаря."""
        data = {
            "decision": "abort",
            "delay_seconds": 0.0,
            "reason": "Решение из словаря",
            "metadata": {"source": "dict", "test": True}
        }
        
        decision = RetryDecision.model_validate(data)
        
        assert decision.decision == "abort"
        assert decision.delay_seconds == 0.0
        assert decision.reason == "Решение из словаря"
        assert decision.metadata == {"source": "dict", "test": True}


class TestRetryResult:
    """Тесты для RetryResult."""
    
    def test_retry_result_creation(self):
        """Тест создания RetryResult."""
        result = RetryResult(
            success=True,
            attempts_made=2,
            final_decision="success",
            error_message=None
        )
        
        assert result.success is True
        assert result.attempts_made == 2
        assert result.final_decision == "success"
        assert result.error_message is None
    
    def test_retry_result_with_error(self):
        """Тест создания RetryResult с ошибкой."""
        result = RetryResult(
            success=False,
            attempts_made=3,
            final_decision="failed",
            error_message="Тестовая ошибка"
        )
        
        assert result.success is False
        assert result.error_message == "Тестовая ошибка"
    
    def test_retry_result_default_values(self):
        """Тест значений по умолчанию для RetryResult."""
        result = RetryResult(
            success=True,
            attempts_made=1
        )
        
        assert result.final_decision is None    # значение по умолчанию
        assert result.error_message is None     # значение по умолчанию
    
    def test_retry_result_equality(self):
        """Тест равенства RetryResult."""
        result1 = RetryResult(
            success=True,
            attempts_made=1,
            final_decision="success"
        )
        
        result2 = RetryResult(
            success=True,
            attempts_made=1,
            final_decision="success"
        )
        
        result3 = RetryResult(
            success=False,  # другое значение
            attempts_made=1,
            final_decision="success"
        )
        
        assert result1 == result2  # одинаковые по значению
        assert result1 != result3  # разные success
        assert result2 != result3  # разные success
    
    def test_retry_result_serialization(self):
        """Тест сериализации RetryResult."""
        result = RetryResult(
            success=True,
            attempts_made=4,
            final_decision="completed",
            error_message=None
        )
        
        data = result.model_dump()
        
        assert data["success"] is True
        assert data["attempts_made"] == 4
        assert data["final_decision"] == "completed"
        assert data["error_message"] is None
    
    def test_retry_result_from_dict(self):
        """Тест создания RetryResult из словаря."""
        data = {
            "success": False,
            "attempts_made": 5,
            "final_decision": "terminated",
            "error_message": "Превышено максимальное количество попыток"
        }
        
        result = RetryResult.model_validate(data)
        
        assert result.success is False
        assert result.attempts_made == 5
        assert result.final_decision == "terminated"
        assert result.error_message == "Превышено максимальное количество попыток"


class TestExecutionErrorInfo:
    """Тесты для ExecutionErrorInfo."""
    
    def test_execution_error_info_creation(self):
        """Тест создания ExecutionErrorInfo."""
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.TRANSIENT,
            message="Тестовая ошибка",
            raw_error=Exception("Тестовое исключение"),
            context={"key": "value"}
        )
        
        assert error_info.category == ErrorCategory.TRANSIENT
        assert error_info.message == "Тестовая ошибка"
        assert str(error_info.raw_error) == "Тестовое исключение"
        assert error_info.context == {"key": "value"}
    
    def test_execution_error_info_with_optional_fields(self):
        """Тест создания ExecutionErrorInfo с опциональными полями."""
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.PERMANENT,
            message="Постоянная ошибка",
            raw_error=ValueError("Значение ошибки"),
            context={"service": "test_service", "endpoint": "/api/test"},
            severity="high",
            recovery_possible=False
        )
        
        assert error_info.severity == "high"
        assert error_info.recovery_possible is False
    
    def test_execution_error_info_default_values(self):
        """Тест значений по умолчанию для ExecutionErrorInfo."""
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.NETWORK,
            message="Сетевая ошибка"
        )
        
        assert error_info.raw_error is None          # значение по умолчанию
        assert error_info.context == {}              # значение по умолчанию
        assert error_info.severity == "medium"       # значение по умолчанию
        assert error_info.recovery_possible is True   # значение по умолчанию
    
    def test_execution_error_info_equality(self):
        """Тест равенства ExecutionErrorInfo."""
        error_info1 = ExecutionErrorInfo(
            category=ErrorCategory.TIMEOUT,
            message="Таймаут",
            raw_error=TimeoutError("Connection timeout")
        )
        
        error_info2 = ExecutionErrorInfo(
            category=ErrorCategory.TIMEOUT,
            message="Таймаут",
            raw_error=TimeoutError("Connection timeout")
        )
        
        error_info3 = ExecutionErrorInfo(
            category=ErrorCategory.VALIDATION,  # другая категория
            message="Таймаут",
            raw_error=TimeoutError("Connection timeout")
        )
        
        assert error_info1 == error_info2  # одинаковые по значению
        assert error_info1 != error_info3  # разные category
        assert error_info2 != error_info3  # разные category
    
    def test_execution_error_info_serialization(self):
        """Тест сериализации ExecutionErrorInfo."""
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.RATE_LIMIT,
            message="Превышено ограничение частоты запросов",
            raw_error=Exception("Rate limit exceeded"),
            context={"requests_per_minute": 60},
            severity="low",
            recovery_possible=True
        )
        
        data = error_info.model_dump()
        
        assert data["category"] == "rate_limit"
        assert data["message"] == "Превышено ограничение частоты запросов"
        assert data["context"] == {"requests_per_minute": 60}
        assert data["severity"] == "low"
        assert data["recovery_possible"] is True
    
    def test_execution_error_info_from_dict(self):
        """Тест создания ExecutionErrorInfo из словаря."""
        data = {
            "category": "authentication",
            "message": "Ошибка аутентификации",
            "raw_error": "Invalid API key",
            "context": {"api_key_last_4": "****5678"},
            "severity": "high",
            "recovery_possible": False
        }
        
        error_info = ExecutionErrorInfo.model_validate(data)
        
        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.message == "Ошибка аутентификации"
        assert error_info.raw_error == "Invalid API key"
        assert error_info.context == {"api_key_last_4": "****5678"}
        assert error_info.severity == "high"
        assert error_info.recovery_possible is False


def test_retry_policy_enum_values_consistency():
    """Тест согласованности значений enum."""
    # Проверяем, что все enum работают корректно
    assert hasattr(ErrorCategory, 'TRANSIENT')
    assert hasattr(RetryDecision, 'decision')
    assert hasattr(RetryResult, 'success')
    assert hasattr(ExecutionErrorInfo, 'category')
    
    # Проверяем, что экземпляры создаются корректно
    error_info = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Тест"
    )
    assert error_info.category == ErrorCategory.TRANSIENT
    assert error_info.message == "Тест"