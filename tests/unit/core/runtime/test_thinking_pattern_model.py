"""
Тесты для модели ThinkingPattern (ThinkingPattern, ThinkingPatternType, StrategyDecision, StrategyDecisionType).
"""
import pytest
from models.thinking_pattern import ThinkingPattern, ThinkingPatternType, StrategyDecision, StrategyDecisionType


class TestThinkingPatternModel:
    """Тесты для модели ThinkingPattern."""
    
    def test_thinking_pattern_creation(self):
        """Тест создания ThinkingPattern."""
        pattern = ThinkingPattern(
            name="test_pattern",
            description="Тестовый паттерн мышления",
            pattern_type=ThinkingPatternType.REACT,
            parameters={"max_iterations": 10, "temperature": 0.7}
        )
        
        assert pattern.name == "test_pattern"
        assert pattern.description == "Тестовый паттерн мышления"
        assert pattern.pattern_type == ThinkingPatternType.REACT
        assert pattern.parameters == {"max_iterations": 10, "temperature": 0.7}
    
    def test_thinking_pattern_with_optional_fields(self):
        """Тест создания ThinkingPattern с опциональными полями."""
        pattern = ThinkingPattern(
            name="advanced_pattern",
            description="Продвинутый паттерн",
            pattern_type=ThinkingPatternType.PLANNING,
            parameters={"iterations": 5},
            enabled=True,
            metadata={"author": "test_author", "version": "1.0"}
        )
        
        assert pattern.enabled is True
        assert pattern.metadata == {"author": "test_author", "version": "1.0"}
    
    def test_thinking_pattern_default_values(self):
        """Тест значений по умолчанию для ThinkingPattern."""
        pattern = ThinkingPattern(
            name="minimal_pattern",
            description="Минимальный паттерн",
            pattern_type=ThinkingPatternType.THINKING
        )
        
        assert pattern.enabled is True      # значение по умолчанию
        assert pattern.metadata == {}       # значение по умолчанию
        assert pattern.parameters == {}     # значение по умолчанию
    
    def test_thinking_pattern_equality(self):
        """Тест равенства ThinkingPattern."""
        pattern1 = ThinkingPattern(
            name="test_pattern",
            description="Тестовый паттерн",
            pattern_type=ThinkingPatternType.REACT,
            parameters={"param": "value"}
        )
        
        pattern2 = ThinkingPattern(
            name="test_pattern",
            description="Тестовый паттерн",
            pattern_type=ThinkingPatternType.REACT,
            parameters={"param": "value"}
        )
        
        pattern3 = ThinkingPattern(
            name="different_pattern",  # другое имя
            description="Тестовый паттерн",
            pattern_type=ThinkingPatternType.REACT,
            parameters={"param": "value"}
        )
        
        assert pattern1 == pattern2  # одинаковые по значению
        assert pattern1 != pattern3  # разные name
        assert pattern2 != pattern3  # разные name
    
    def test_thinking_pattern_serialization(self):
        """Тест сериализации ThinkingPattern."""
        pattern = ThinkingPattern(
            name="serialize_pattern",
            description="Паттерн для сериализации",
            pattern_type=ThinkingPatternType.EVALUATION,
            parameters={"eval_param": "eval_value"},
            enabled=True,
            metadata={"category": "test", "complexity": "medium"}
        )
        
        data = pattern.model_dump()
        
        assert data["name"] == "serialize_pattern"
        assert data["description"] == "Паттерн для сериализации"
        assert data["pattern_type"] == "evaluation"
        assert data["parameters"] == {"eval_param": "eval_value"}
        assert data["enabled"] is True
        assert data["metadata"] == {"category": "test", "complexity": "medium"}
    
    def test_thinking_pattern_from_dict(self):
        """Тест создания ThinkingPattern из словаря."""
        data = {
            "name": "dict_pattern",
            "description": "Паттерн из словаря",
            "pattern_type": "planning",
            "parameters": {"plan_param": "plan_value"},
            "enabled": False,
            "metadata": {"source": "dictionary", "test": True}
        }
        
        pattern = ThinkingPattern.model_validate(data)
        
        assert pattern.name == "dict_pattern"
        assert pattern.description == "Паттерн из словаря"
        assert pattern.pattern_type == ThinkingPatternType.PLANNING
        assert pattern.parameters == {"plan_param": "plan_value"}
        assert pattern.enabled is False
        assert pattern.metadata == {"source": "dictionary", "test": True}


class TestStrategyDecisionModel:
    """Тесты для модели StrategyDecision."""
    
    def test_strategy_decision_creation(self):
        """Тест создания StrategyDecision."""
        decision = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"capability": "test_capability", "params": {"param": "value"}},
            reason="Тестовое решение",
            next_strategy="react"
        )
        
        assert decision.action == StrategyDecisionType.ACT
        assert decision.payload == {"capability": "test_capability", "params": {"param": "value"}}
        assert decision.reason == "Тестовое решение"
        assert decision.next_strategy == "react"
    
    def test_strategy_decision_with_optional_fields(self):
        """Тест создания StrategyDecision с опциональными полями."""
        decision = StrategyDecision(
            action=StrategyDecisionType.THINK,
            payload={"thought": "thinking_process"},
            reason="Рассуждение",
            next_strategy="planning",
            confidence=0.9,
            metadata={"source": "llm", "tokens_used": 45}
        )
        
        assert decision.confidence == 0.9
        assert decision.metadata == {"source": "llm", "tokens_used": 45}
    
    def test_strategy_decision_minimal_creation(self):
        """Тест создания StrategyDecision с минимальными полями."""
        decision = StrategyDecision(
            action=StrategyDecisionType.OBSERVE,
            reason="Простое наблюдение"
        )
        
        assert decision.action == StrategyDecisionType.OBSERVE
        assert decision.reason == "Простое наблюдение"
        assert decision.payload is None          # значение по умолчанию
        assert decision.next_strategy is None    # значение по умолчанию
        assert decision.confidence is None       # значение по умолчанию
        assert decision.metadata == {}           # значение по умолчанию
    
    def test_strategy_decision_equality(self):
        """Тест равенства StrategyDecision."""
        decision1 = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "value"},
            reason="Тестовое решение"
        )
        
        decision2 = StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={"test": "value"},
            reason="Тестовое решение"
        )
        
        decision3 = StrategyDecision(
            action=StrategyDecisionType.THINK,  # другое действие
            payload={"test": "value"},
            reason="Тестовое решение"
        )
        
        assert decision1 == decision2  # одинаковые по значению
        assert decision1 != decision3  # разные action
        assert decision2 != decision3  # разные action
    
    def test_strategy_decision_serialization(self):
        """Тест сериализации StrategyDecision."""
        decision = StrategyDecision(
            action=StrategyDecisionType.STOP,
            payload={"result": "final_answer"},
            reason="Цель достигнута",
            next_strategy=None,
            confidence=0.95,
            metadata={"completion_reason": "goal_achieved", "steps_taken": 5}
        )
        
        data = decision.model_dump()
        
        assert data["action"] == "stop"
        assert data["payload"] == {"result": "final_answer"}
        assert data["reason"] == "Цель достигнута"
        assert data["next_strategy"] is None
        assert data["confidence"] == 0.95
        assert data["metadata"] == {"completion_reason": "goal_achieved", "steps_taken": 5}
    
    def test_strategy_decision_from_dict(self):
        """Тест создания StrategyDecision из словаря."""
        data = {
            "action": "switch",
            "payload": {"new_strategy": "fallback"},
            "reason": "Ошибка в текущей стратегии",
            "next_strategy": "fallback_strategy",
            "confidence": 0.8,
            "metadata": {"error_type": "execution_error", "recovery_attempts": 1}
        }
        
        decision = StrategyDecision.model_validate(data)
        
        assert decision.action == StrategyDecisionType.SWITCH
        assert decision.payload == {"new_strategy": "fallback"}
        assert decision.reason == "Ошибка в текущей стратегии"
        assert decision.next_strategy == "fallback_strategy"
        assert decision.confidence == 0.8
        assert decision.metadata == {"error_type": "execution_error", "recovery_attempts": 1}


def test_thinking_pattern_type_enum_values():
    """Тест значений ThinkingPatternType enum."""
    assert ThinkingPatternType.REACT.value == "react"
    assert ThinkingPatternType.PLANNING.value == "planning"
    assert ThinkingPatternType.THINKING.value == "thinking"
    assert ThinkingPatternType.EVALUATION.value == "evaluation"
    assert ThinkingPatternType.FALLBACK.value == "fallback"
    assert ThinkingPatternType.SEQUENTIAL.value == "sequential"
    assert ThinkingPatternType.PARALLEL.value == "parallel"
    
    # Проверяем все значения
    all_types = [tp_type.value for tp_type in ThinkingPatternType]
    expected_types = [
        "react", "planning", "thinking", "evaluation", 
        "fallback", "sequential", "parallel"
    ]
    assert set(all_types) == set(expected_types)


def test_strategy_decision_type_enum_values():
    """Тест значений StrategyDecisionType enum."""
    assert StrategyDecisionType.ACT.value == "act"
    assert StrategyDecisionType.THINK.value == "think"
    assert StrategyDecisionType.OBSERVE.value == "observe"
    assert StrategyDecisionType.STOP.value == "stop"
    assert StrategyDecisionType.SWITCH.value == "switch"
    assert StrategyDecisionType.WAIT.value == "wait"
    
    # Проверяем все значения
    all_types = [sd_type.value for sd_type in StrategyDecisionType]
    expected_types = ["act", "think", "observe", "stop", "switch", "wait"]
    assert set(all_types) == set(expected_types)