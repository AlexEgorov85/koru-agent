"""
Тесты для модели ExecutionStrategy (ExecutionStrategy, ExecutionStrategyType, StrategyConfig, StrategyResult).
"""
import pytest
from models.execution_strategy import ExecutionStrategy, ExecutionStrategyType, StrategyConfig, StrategyResult, StrategyStatus


class TestExecutionStrategyModel:
    """Тесты для модели ExecutionStrategy."""
    
    def test_execution_strategy_creation(self):
        """Тест создания ExecutionStrategy."""
        strategy = ExecutionStrategy(
            name="test_strategy",
            description="Тестовая стратегия выполнения",
            strategy_type=ExecutionStrategyType.REACT,
            parameters={"max_steps": 10, "temperature": 0.7}
        )
        
        assert strategy.name == "test_strategy"
        assert strategy.description == "Тестовая стратегия выполнения"
        assert strategy.strategy_type == ExecutionStrategyType.REACT
        assert strategy.parameters == {"max_steps": 10, "temperature": 0.7}
    
    def test_execution_strategy_with_optional_fields(self):
        """Тест создания ExecutionStrategy с опциональными полями."""
        strategy = ExecutionStrategy(
            name="advanced_strategy",
            description="Продвинутая стратегия",
            strategy_type=ExecutionStrategyType.PLANNING,
            parameters={"planning_depth": 5},
            enabled=True,
            metadata={"author": "test_author", "version": "1.0"}
        )
        
        assert strategy.enabled is True
        assert strategy.metadata == {"author": "test_author", "version": "1.0"}
    
    def test_execution_strategy_default_values(self):
        """Тест значений по умолчанию для ExecutionStrategy."""
        strategy = ExecutionStrategy(
            name="minimal_strategy",
            description="Минимальная стратегия",
            strategy_type=ExecutionStrategyType.THINKING
        )
        
        assert strategy.enabled is True      # значение по умолчанию
        assert strategy.metadata == {}       # значение по умолчанию
        assert strategy.parameters == {}     # значение по умолчанию
    
    def test_execution_strategy_equality(self):
        """Тест равенства ExecutionStrategy."""
        strategy1 = ExecutionStrategy(
            name="test_strategy",
            description="Тестовая стратегия",
            strategy_type=ExecutionStrategyType.REACT,
            parameters={"param": "value"}
        )
        
        strategy2 = ExecutionStrategy(
            name="test_strategy",
            description="Тестовая стратегия",
            strategy_type=ExecutionStrategyType.REACT,
            parameters={"param": "value"}
        )
        
        strategy3 = ExecutionStrategy(
            name="different_strategy",  # другое имя
            description="Тестовая стратегия",
            strategy_type=ExecutionStrategyType.REACT,
            parameters={"param": "value"}
        )
        
        assert strategy1 == strategy2  # одинаковые по значению
        assert strategy1 != strategy3  # разные name
        assert strategy2 != strategy3  # разные name
    
    def test_execution_strategy_serialization(self):
        """Тест сериализации ExecutionStrategy."""
        strategy = ExecutionStrategy(
            name="serialize_strategy",
            description="Стратегия для сериализации",
            strategy_type=ExecutionStrategyType.EVALUATION,
            parameters={"eval_param": "eval_value"},
            enabled=True,
            metadata={"category": "test", "complexity": "medium"}
        )
        
        data = strategy.model_dump()
        
        assert data["name"] == "serialize_strategy"
        assert data["description"] == "Стратегия для сериализации"
        assert data["strategy_type"] == "evaluation"
        assert data["parameters"] == {"eval_param": "eval_value"}
        assert data["enabled"] is True
        assert data["metadata"] == {"category": "test", "complexity": "medium"}
    
    def test_execution_strategy_from_dict(self):
        """Тест создания ExecutionStrategy из словаря."""
        data = {
            "name": "dict_strategy",
            "description": "Стратегия из словаря",
            "strategy_type": "planning",
            "parameters": {"plan_param": "plan_value"},
            "enabled": False,
            "metadata": {"source": "dictionary", "test": True}
        }
        
        strategy = ExecutionStrategy.model_validate(data)
        
        assert strategy.name == "dict_strategy"
        assert strategy.description == "Стратегия из словаря"
        assert strategy.strategy_type == ExecutionStrategyType.PLANNING
        assert strategy.parameters == {"plan_param": "plan_value"}
        assert strategy.enabled is False
        assert strategy.metadata == {"source": "dictionary", "test": True}


class TestStrategyConfigModel:
    """Тесты для модели StrategyConfig."""
    
    def test_strategy_config_creation(self):
        """Тест создания StrategyConfig."""
        config = StrategyConfig(
            name="test_config",
            strategy_name="test_strategy",
            parameters={"temperature": 0.7, "max_tokens": 1024},
            enabled=True
        )
        
        assert config.name == "test_config"
        assert config.strategy_name == "test_strategy"
        assert config.parameters == {"temperature": 0.7, "max_tokens": 1024}
        assert config.enabled is True
    
    def test_strategy_config_with_optional_fields(self):
        """Тест создания StrategyConfig с опциональными полями."""
        config = StrategyConfig(
            name="advanced_config",
            strategy_name="advanced_strategy",
            parameters={"param1": "value1", "param2": 42},
            enabled=True,
            metadata={"environment": "development", "priority": 1}
        )
        
        assert config.metadata == {"environment": "development", "priority": 1}
    
    def test_strategy_config_default_values(self):
        """Тест значений по умолчанию для StrategyConfig."""
        config = StrategyConfig(
            name="minimal_config",
            strategy_name="minimal_strategy"
        )
        
        assert config.parameters == {}    # значение по умолчанию
        assert config.enabled is True     # значение по умолчанию
        assert config.metadata == {}      # значение по умолчанию
    
    def test_strategy_config_equality(self):
        """Тест равенства StrategyConfig."""
        config1 = StrategyConfig(
            name="test_config",
            strategy_name="test_strategy",
            parameters={"param": "value"}
        )
        
        config2 = StrategyConfig(
            name="test_config",
            strategy_name="test_strategy",
            parameters={"param": "value"}
        )
        
        config3 = StrategyConfig(
            name="different_config",  # другое имя
            strategy_name="test_strategy",
            parameters={"param": "value"}
        )
        
        assert config1 == config2  # одинаковые по значению
        assert config1 != config3  # разные name
        assert config2 != config3  # разные name
    
    def test_strategy_config_serialization(self):
        """Тест сериализации StrategyConfig."""
        config = StrategyConfig(
            name="serialize_config",
            strategy_name="serialize_strategy",
            parameters={"serialize_param": "serialize_value"},
            enabled=False,
            metadata={"exported": True, "format": "json"}
        )
        
        data = config.model_dump()
        
        assert data["name"] == "serialize_config"
        assert data["strategy_name"] == "serialize_strategy"
        assert data["parameters"] == {"serialize_param": "serialize_value"}
        assert data["enabled"] is False
        assert data["metadata"] == {"exported": True, "format": "json"}
    
    def test_strategy_config_from_dict(self):
        """Тест создания StrategyConfig из словаря."""
        data = {
            "name": "dict_config",
            "strategy_name": "dict_strategy",
            "parameters": {"dict_param": "dict_value"},
            "enabled": True,
            "metadata": {"imported": True, "source": "api"}
        }
        
        config = StrategyConfig.model_validate(data)
        
        assert config.name == "dict_config"
        assert config.strategy_name == "dict_strategy"
        assert config.parameters == {"dict_param": "dict_value"}
        assert config.enabled is True
        assert config.metadata == {"imported": True, "source": "api"}


class TestStrategyResultModel:
    """Тесты для модели StrategyResult."""
    
    def test_strategy_result_creation(self):
        """Тест создания StrategyResult."""
        result = StrategyResult(
            status="success",
            result_data={"answer": "test_answer", "confidence": 0.95},
            metadata={"tokens_used": 45, "execution_time": 0.5}
        )
        
        assert result.status == "success"
        assert result.result_data == {"answer": "test_answer", "confidence": 0.95}
        assert result.metadata == {"tokens_used": 45, "execution_time": 0.5}
    
    def test_strategy_result_with_optional_fields(self):
        """Тест создания StrategyResult с опциональными полями."""
        result = StrategyResult(
            status="partial",
            result_data={"partial_result": "incomplete"},
            error="Временная ошибка",
            metadata={"retry_count": 2, "warning": "Low confidence"}
        )
        
        assert result.status == "partial"
        assert result.error == "Временная ошибка"
        assert result.metadata == {"retry_count": 2, "warning": "Low confidence"}
    
    def test_strategy_result_default_values(self):
        """Тест значений по умолчанию для StrategyResult."""
        result = StrategyResult(
            status="success",
            result_data={"test": "value"}
        )
        
        assert result.error is None     # значение по умолчанию
        assert result.metadata == {}    # значение по умолчанию
    
    def test_strategy_result_equality(self):
        """Тест равенства StrategyResult."""
        result1 = StrategyResult(
            status="success",
            result_data={"data": "value"}
        )
        
        result2 = StrategyResult(
            status="success",
            result_data={"data": "value"}
        )
        
        result3 = StrategyResult(
            status="failed",  # другой статус
            result_data={"data": "value"}
        )
        
        assert result1 == result2  # одинаковые по значению
        assert result1 != result3  # разные status
        assert result2 != result3  # разные status
    
    def test_strategy_result_serialization(self):
        """Тест сериализации StrategyResult."""
        result = StrategyResult(
            status="error",
            result_data={"error_result": "detailed_error"},
            error="Подробное сообщение об ошибке",
            metadata={"error_code": 500, "timestamp": "2023-01-01T00:00:00Z"}
        )
        
        data = result.model_dump()
        
        assert data["status"] == "error"
        assert data["result_data"] == {"error_result": "detailed_error"}
        assert data["error"] == "Подробное сообщение об ошибке"
        assert data["metadata"] == {"error_code": 500, "timestamp": "2023-01-01T00:00:00Z"}
    
    def test_strategy_result_from_dict(self):
        """Тест создания StrategyResult из словаря."""
        data = {
            "status": "timeout",
            "result_data": {"timeout_result": "partial_data"},
            "error": "Таймаут выполнения",
            "metadata": {"timeout_seconds": 30, "recovered": False}
        }
        
        result = StrategyResult.model_validate(data)
        
        assert result.status == "timeout"
        assert result.result_data == {"timeout_result": "partial_data"}
        assert result.error == "Таймаут выполнения"
        assert result.metadata == {"timeout_seconds": 30, "recovered": False}


def test_execution_strategy_type_enum_values():
    """Тест значений ExecutionStrategyType enum."""
    assert ExecutionStrategyType.REACT.value == "react"
    assert ExecutionStrategyType.PLANNING.value == "planning"
    assert ExecutionStrategyType.THINKING.value == "thinking"
    assert ExecutionStrategyType.EVALUATION.value == "evaluation"
    assert ExecutionStrategyType.FALLBACK.value == "fallback"
    assert ExecutionStrategyType.SEQUENTIAL.value == "sequential"
    assert ExecutionStrategyType.PARALLEL.value == "parallel"
    
    # Проверяем все значения
    all_types = [es_type.value for es_type in ExecutionStrategyType]
    expected_types = [
        "react", "planning", "thinking", "evaluation", 
        "fallback", "sequential", "parallel"
    ]
    assert set(all_types) == set(expected_types)


def test_strategy_status_enum_values():
    """Тест значений StrategyStatus enum."""
    assert StrategyStatus.SUCCESS.value == "success"
    assert StrategyStatus.FAILED.value == "failed"
    assert StrategyStatus.PARTIAL.value == "partial"
    assert StrategyStatus.TIMEOUT.value == "timeout"
    assert StrategyStatus.CANCELLED.value == "cancelled"
    assert StrategyStatus.RUNNING.value == "running"
    assert StrategyStatus.PENDING.value == "pending"
    
    # Проверяем все значения
    all_statuses = [status.value for status in StrategyStatus]
    expected_statuses = [
        "success", "failed", "partial", "timeout", 
        "cancelled", "running", "pending"
    ]
    assert set(all_statuses) == set(expected_statuses)