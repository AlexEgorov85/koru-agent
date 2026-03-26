"""
Тесты валидации контрактов для behavior patterns.

ПРИМЕЧАНИЕ: Тесты используют реальные объекты вместо моков для ApplicationContext и сервисов.
Моки допускаются только для LLM и БД провайдеров.
"""
import pytest
from core.config.component_config import ComponentConfig


class TestBehaviorContractsValidation:
    """Тесты валидации контрактов behavior patterns."""

    @pytest.mark.asyncio
    async def test_component_config_creation(self):
        """Тест создания ComponentConfig для behavior patterns."""
        config = ComponentConfig(
            variant_id="test_react_pattern_default",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )

        assert config is not None
        assert config.variant_id == "test_react_pattern_default"
        assert config.side_effects_enabled is True
        assert config.detailed_metrics is False

    @pytest.mark.asyncio
    async def test_component_config_with_prompt_versions(self):
        """Тест ComponentConfig с версиями промптов."""
        config = ComponentConfig(
            variant_id="test_planning_pattern_v1",
            prompt_versions={
                "behavior.planning.decompose": "v1.0",
                "behavior.planning.sequence": "v1.0"
            },
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )

        assert config.prompt_versions["behavior.planning.decompose"] == "v1.0"
        assert config.prompt_versions["behavior.planning.sequence"] == "v1.0"


class TestBehaviorPatternStructure:
    """Тесты структуры behavior patterns."""

    def test_react_pattern_has_required_attributes(self):
        """Тест наличия обязательных атрибутов у ReActPattern."""
        from core.agent.behaviors.base import ReActInput, ReActOutput

        # Проверяем наличие классов входа/выхода
        assert ReActInput is not None
        assert ReActOutput is not None

        # Проверяем атрибуты ReActInput
        input_obj = ReActInput(goal="Test goal")
        assert input_obj.goal == "Test goal"
        assert input_obj.context == {}
        assert input_obj.history == []
        assert input_obj.available_tools == []

        # Проверяем атрибуты ReActOutput
        output_obj = ReActOutput(thought="Test thought", is_final=False)
        assert output_obj.thought == "Test thought"
        assert output_obj.is_final is False

    def test_planning_pattern_has_required_attributes(self):
        """Тест наличия обязательных атрибутов у PlanningPattern."""
        from core.agent.behaviors.base import PlanningInput, PlanningOutput

        assert PlanningInput is not None
        assert PlanningOutput is not None

        # Проверяем атрибуты PlanningInput
        input_obj = PlanningInput(goal="Test goal")
        assert input_obj.goal == "Test goal"
        assert input_obj.context == {}
        assert input_obj.available_tools == []
        assert input_obj.constraints == []
        
        # Проверяем атрибуты PlanningOutput
        output_obj = PlanningOutput(plan=[], is_complete=False)
        assert output_obj.plan == []
        assert output_obj.is_complete is False

    def test_evaluation_pattern_has_required_attributes(self):
        """Тест наличия обязательных атрибутов у EvaluationPattern."""
        from core.agent.behaviors.evaluation.pattern import EvaluationPattern
        from core.config.component_config import ComponentConfig
        from unittest.mock import Mock

        # Создаём минимальный ComponentConfig для теста
        config = ComponentConfig(variant_id="test_evaluation")
        
        # Создаём mock executor (требуется архитектурой)
        mock_executor = Mock()

        pattern = EvaluationPattern(
            component_name="test_evaluation_pattern", 
            component_config=config,
            executor=mock_executor
        )
        assert pattern.pattern_id == "test_evaluation_pattern"
        assert hasattr(pattern, 'analyze_context')
        assert hasattr(pattern, 'generate_decision')

    def test_fallback_pattern_has_required_attributes(self):
        """Тест наличия обязательных атрибутов у FallbackPattern."""
        from core.agent.behaviors.fallback.pattern import FallbackPattern
        from core.config.component_config import ComponentConfig
        from unittest.mock import Mock

        # Создаём минимальный ComponentConfig для теста
        config = ComponentConfig(variant_id="test_fallback")
        
        # Создаём mock executor (требуется архитектурой)
        mock_executor = Mock()

        pattern = FallbackPattern(
            component_name="test_fallback_pattern", 
            component_config=config,
            executor=mock_executor
        )
        assert pattern.pattern_id == "test_fallback_pattern"
        assert hasattr(pattern, 'analyze_context')
        assert hasattr(pattern, 'generate_decision')


class TestBehaviorDecisionTypes:
    """Тесты типов решений behavior patterns."""

    def test_behavior_decision_type_values(self):
        """Тест значений BehaviorDecisionType."""
        from core.agent.behaviors.base import BehaviorDecisionType
        
        assert BehaviorDecisionType.ACT.value == "act"
        assert BehaviorDecisionType.STOP.value == "stop"
        assert BehaviorDecisionType.SWITCH.value == "switch"
        assert BehaviorDecisionType.RETRY.value == "retry"

    def test_behavior_decision_creation(self):
        """Тест создания BehaviorDecision."""
        from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
        
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test_capability",
            parameters={"key": "value"},
            reason="test_reason",
            confidence=0.95
        )
        
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name == "test_capability"
        assert decision.parameters == {"key": "value"}
        assert decision.reason == "test_reason"
        assert decision.confidence == 0.95

    def test_behavior_decision_switch_type(self):
        """Тест создания BehaviorDecision для SWITCH."""
        from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
        
        decision = BehaviorDecision(
            action=BehaviorDecisionType.SWITCH,
            next_pattern="planning.v1.0.0",
            parameters={"refined_goal": "new goal"},
            reason="partial_progress"
        )
        
        assert decision.action == BehaviorDecisionType.SWITCH
        assert decision.next_pattern == "planning.v1.0.0"
        assert decision.parameters["refined_goal"] == "new goal"
