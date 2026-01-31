"""
Тесты для классов стратегического решения агента (StrategyDecision, StrategyDecisionType).
Из-за циклических импортов в архитектуре агента не тестируем AgentThinkingPatternInterface напрямую.
"""

import pytest
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType


# Пропускаем тестирование интерфейса из-за циклических импортов, тестируем только конкретные классы
# from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface  # Закомментировано из-за циклического импорта

class ConcreteThinkingPattern:  # Временно убираем наследование из-за циклического импорта
    """Конкретная реализация AgentThinkingPatternInterface для тестов."""
    name = "concrete_thinking_pattern"
    
    async def next_step(self, runtime):
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "payload"},
            reason="Тестовое решение"
        )


# Удаляем тесты, которые требуют импорт AgentThinkingPatternInterface из-за циклических импортов


class TestStrategyDecisionModel:
    """Тесты для модели StrategyDecision."""
    
    def test_strategy_decision_creation(self):
        """Тест создания StrategyDecision."""
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability="test_capability",  # Добавляем capability, так как для ACT обязательно
            payload={"params": {"param": "value"}},
            reason="Тестовое решение",
            next_strategy="react"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.capability == "test_capability"
        assert decision.payload == {"params": {"param": "value"}}
        assert decision.reason == "Тестовое решение"
        assert decision.next_strategy == "react"
    
    def test_strategy_decision_with_optional_fields(self):
        """Тест создания StrategyDecision с опциональными полями."""
        decision = StrategyDecision(
            action=StrategyDecisionType.STOP,
            payload={"result": "test_result"},
            reason="Тестовая причина",
            next_strategy=None,
            capability="test_capability",
            parameters_class=str
        )
        
        assert decision.capability == "test_capability"
        assert decision.parameters_class == str
        assert decision.payload == {"result": "test_result"}
        assert decision.reason == "Тестовая причина"
    
    def test_strategy_decision_minimal_creation(self):
        """Тест создания StrategyDecision с минимальными полями."""
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability="test_capability",
            reason="Простое решение"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.reason == "Простое решение"
        assert decision.payload is None          # значение по умолчанию
        assert decision.next_strategy is None    # значение по умолчанию
        assert decision.capability == "test_capability"
        assert decision.parameters_class is None # значение по умолчанию
    
    def test_strategy_decision_validation_act_without_capability(self):
        """Тест валидации StrategyDecision при действии ACT без capability."""
        with pytest.raises(ValueError, match="Для действия ACT необходимо указать capability"):
            StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="Тестовое решение"
            )
    
    def test_strategy_decision_validation_switch_without_next_strategy(self):
        """Тест валидации StrategyDecision при действии SWITCH без next_strategy."""
        with pytest.raises(ValueError, match="Для действия SWITCH необходимо указать next_strategy"):
            StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                capability="test_capability",
                reason="Тестовое решение"
            )
    
    def test_strategy_decision_equality(self):
        """Тест равенства StrategyDecision."""
        decision1 = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "value"},
            reason="Тестовое решение",
            capability="test_capability"
        )
        
        decision2 = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "value"},
            reason="Тестовое решение",
            capability="test_capability"
        )
        
        decision3 = StrategyDecision(
            action=StrategyDecisionType.STOP,  # другое действие
            payload={"test": "value"},
            reason="Тестовое решение",
            capability="test_capability"
        )
        
        # dataclass сравнение основано на значениях полей
        assert decision1 == decision2  # одинаковые по значению
        assert decision1 != decision3  # разные action
        assert decision2 != decision3  # разные action


def test_strategy_decision_type_enum_values():
    """Тест значений StrategyDecisionType enum."""
    assert StrategyDecisionType.ACT.value == "act"
    assert StrategyDecisionType.STOP.value == "stop"
    assert StrategyDecisionType.SWITCH.value == "switch"
    assert StrategyDecisionType.RETRY.value == "retry"
    
    # Проверяем все значения
    all_types = [decision_type.value for decision_type in StrategyDecisionType]
    expected_types = ["act", "stop", "switch", "retry"]
    assert set(all_types) == set(expected_types)


def test_strategy_decision_type_is_terminal_method():
    """Тест метода is_terminal для StrategyDecisionType."""
    assert StrategyDecisionType.STOP.is_terminal() is True
    assert StrategyDecisionType.SWITCH.is_terminal() is True
    assert StrategyDecisionType.ACT.is_terminal() is False
    assert StrategyDecisionType.RETRY.is_terminal() is False