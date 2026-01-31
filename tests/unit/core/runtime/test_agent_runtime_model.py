"""
Тесты для моделей в agent_runtime.model.
"""
import pytest
from core.agent_runtime.model import (
    StrategyDecision,
    StrategyDecisionType
)


class TestStrategyDecisionType:
    """Тесты для StrategyDecisionType."""
    
    def test_strategy_decision_type_values(self):
        """Тест значений StrategyDecisionType."""
        assert StrategyDecisionType.ACT.value == "act"
        assert StrategyDecisionType.STOP.value == "stop"
        assert StrategyDecisionType.SWITCH.value == "switch"
        assert StrategyDecisionType.RETRY.value == "retry"
    
    def test_is_terminal_method(self):
        """Тест метода is_terminal."""
        # Терминальные действия
        assert StrategyDecisionType.STOP.is_terminal() is True
        assert StrategyDecisionType.SWITCH.is_terminal() is True
        
        # Не терминальные действия
        assert StrategyDecisionType.ACT.is_terminal() is False
        assert StrategyDecisionType.RETRY.is_terminal() is False


class TestStrategyDecision:
    """Тесты для StrategyDecision."""
    
    def test_strategy_decision_creation(self):
        """Тест создания StrategyDecision."""
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "value"},
            reason="Test reason",
            next_strategy="react"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.payload == {"test": "value"}
        assert decision.reason == "Test reason"
        assert decision.next_strategy == "react"
    
    def test_strategy_decision_optional_fields(self):
        """Тест необязательных полей StrategyDecision."""
        decision = StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason="Stop reason"
        )
        
        assert decision.action == StrategyDecisionType.STOP
        assert decision.reason == "Stop reason"
        assert decision.payload is None
        assert decision.next_strategy is None
        assert decision.parameters_class is None
    
    def test_strategy_decision_with_capability(self):
        """Тест StrategyDecision с capability."""
        mock_capability = type('MockCapability', (), {})()
        
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=mock_capability,
            reason="Execute with capability"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.capability == mock_capability
        assert decision.reason == "Execute with capability"
    
    def test_strategy_decision_with_parameters_class(self):
        """Тест StrategyDecision с parameters_class."""
        class MockParamsClass:
            pass
        
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            parameters_class=MockParamsClass,
            reason="With parameters class"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.parameters_class == MockParamsClass
        assert decision.reason == "With parameters class"
    
    def test_strategy_decision_with_complex_payload(self):
        """Тест StrategyDecision со сложным payload."""
        complex_payload = {
            "capability": "test_capability",
            "parameters": {
                "param1": "value1",
                "param2": [1, 2, 3],
                "nested": {
                    "key": "value"
                }
            },
            "metadata": {
                "priority": 1,
                "tags": ["important", "critical"]
            }
        }
        
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload=complex_payload,
            reason="Complex action"
        )
        
        assert decision.payload == complex_payload
        assert decision.reason == "Complex action"
    
    def test_strategy_decision_validation_act_requires_capability(self):
        """Тест валидации: для ACT требуется capability."""
        with pytest.raises(ValueError, match="Для действия ACT необходимо указать capability"):
            StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="Need capability for ACT"
            )
    
    def test_strategy_decision_validation_switch_requires_next_strategy(self):
        """Тест валидации: для SWITCH требуется next_strategy."""
        with pytest.raises(ValueError, match="Для действия SWITCH необходимо указать next_strategy"):
            StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                reason="Need next strategy for SWITCH"
            )
    
    def test_strategy_decision_valid_act_with_capability(self):
        """Тест корректного создания StrategyDecision с ACT и capability."""
        mock_capability = type('MockCapability', (), {})()
        
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=mock_capability,
            reason="Valid ACT with capability"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.capability == mock_capability
        assert decision.reason == "Valid ACT with capability"
    
    def test_strategy_decision_valid_switch_with_next_strategy(self):
        """Тест корректного создания StrategyDecision с SWITCH и next_strategy."""
        decision = StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="new_strategy",
            reason="Valid SWITCH with next strategy"
        )
        
        assert decision.action == StrategyDecisionType.SWITCH
        assert decision.next_strategy == "new_strategy"
        assert decision.reason == "Valid SWITCH with next strategy"


def test_enums_immutability():
    """Тест, что enum значения неизменяемы."""
    # Проверяем, что нельзя изменить значение enum
    original_value = StrategyDecisionType.ACT.value
    
    # Попытка изменить значение не должна повлиять на оригинальное
    try:
        StrategyDecisionType.ACT.value = "different_value"
    except AttributeError:
        # Это нормально для правильно определенных enum
        pass
    
    # Значение должно остаться прежним
    assert StrategyDecisionType.ACT.value == original_value


def test_object_creation_consistency(self):
    """Тест согласованности создания объектов."""
    # Создаем объекты несколькими способами и проверяем их консистентность
    mock_capability = type('MockCapability', (), {})()
    
    decision1 = StrategyDecision(
        action=StrategyDecisionType.ACT,
        capability=mock_capability,
        reason="Test"
    )
    
    decision2 = StrategyDecision(
        action=StrategyDecisionType.ACT,
        capability=mock_capability,
        reason="Test"
    )
    
    # Два одинаковых решения должны быть равны
    assert decision1.action == decision2.action
    assert decision1.capability == decision2.capability
    assert decision1.reason == decision2.reason
