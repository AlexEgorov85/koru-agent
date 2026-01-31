"""
Тесты для модели ExecutionResult.
"""
import pytest
from models.execution import ExecutionResult, ExecutionStatus


class TestExecutionResultModel:
    """Тесты для модели ExecutionResult."""
    
    def test_execution_result_creation(self):
        """Тест создания ExecutionResult."""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"data": "test_result"},
            observation_item_id="obs_123",
            summary="Тестовое выполнение завершено",
            error=None
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"data": "test_result"}
        assert result.observation_item_id == "obs_123"
        assert result.summary == "Тестовое выполнение завершено"
        assert result.error is None
    
    def test_execution_result_with_error(self):
        """Тест создания ExecutionResult с ошибкой."""
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id="obs_456",
            summary="Ошибка выполнения",
            error="Тестовая ошибка"
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert result.result is None
        assert result.observation_item_id == "obs_456"
        assert result.summary == "Ошибка выполнения"
        assert result.error == "Тестовая ошибка"
    
    def test_execution_result_optional_fields(self):
        """Тест необязательных полей ExecutionResult."""
        result = ExecutionResult(
            status=ExecutionStatus.PENDING,
            result={"partial": "data"}
        )
        
        assert result.status == ExecutionStatus.PENDING
        assert result.result == {"partial": "data"}
        assert result.observation_item_id is None  # по умолчанию
        assert result.summary is None              # по умолчанию
        assert result.error is None                # по умолчанию
    
    def test_execution_result_equality(self):
        """Тест равенства ExecutionResult."""
        result1 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"test": "value"},
            observation_item_id="obs_1",
            summary="Test summary",
            error=None
        )
        
        result2 = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"test": "value"},
            observation_item_id="obs_1",
            summary="Test summary",
            error=None
        )
        
        result3 = ExecutionResult(
            status=ExecutionStatus.FAILED,  # другой статус
            result={"test": "value"},
            observation_item_id="obs_1",
            summary="Test summary",
            error=None
        )
        
        assert result1 == result2  # одинаковые по значению
        assert result1 != result3  # разные status
        assert result2 != result3  # разные status
    
    def test_execution_result_serialization(self):
        """Тест сериализации ExecutionResult."""
        execution_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"key": "value"},
            observation_item_id="obs_789",
            summary="Successful execution",
            error=None
        )
        
        data = execution_result.model_dump()
        
        assert data["status"] == "success"
        assert data["result"] == {"key": "value"}
        assert data["observation_item_id"] == "obs_789"
        assert data["summary"] == "Successful execution"
        assert data["error"] is None
    
    def test_execution_result_from_dict(self):
        """Тест создания ExecutionResult из словаря."""
        data = {
            "status": "failed",
            "result": {"error_data": "something went wrong"},
            "observation_item_id": "obs_error",
            "summary": "Execution failed",
            "error": "Something went wrong"
        }
        
        result = ExecutionResult.model_validate(data)
        
        assert result.status == ExecutionStatus.FAILED
        assert result.result == {"error_data": "something went wrong"}
        assert result.observation_item_id == "obs_error"
        assert result.summary == "Execution failed"
        assert result.error == "Something went wrong"


def test_execution_status_enum_values():
    """Тест значений ExecutionStatus enum."""
    assert ExecutionStatus.SUCCESS.value == "success"
    assert ExecutionStatus.FAILED.value == "failed"
    assert ExecutionStatus.PENDING.value == "pending"
    assert ExecutionStatus.RUNNING.value == "running"
    assert ExecutionStatus.CANCELLED.value == "cancelled"
    
    # Проверяем все значения
    all_statuses = [status.value for status in ExecutionStatus]
    expected_statuses = ["success", "failed", "pending", "running", "cancelled"]
    assert set(all_statuses) == set(expected_statuses)