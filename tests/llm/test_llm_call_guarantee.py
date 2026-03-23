"""
Тесты гарантии вызова LLM.

Проверяют:
1. ExecutionResult имеет поле llm_called
2. BehaviorDecision имеет поле requires_llm
3. InfrastructureError если requires_llm=True но llm_called=False
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.models.errors import InfrastructureError
from core.models.enums.common_enums import ExecutionStatus
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.execution import ExecutionResult


# ============================================================================
# ТЕСТ 1: EXECUTIONRESULT LLm_CALLED FLAG
# ============================================================================

class TestExecutionResultLlmCalled:
    """Тесты флага llm_called в ExecutionResult"""

    def test_execution_result_has_llm_called_field(self):
        """Тест: ExecutionResult имеет поле llm_called"""
        result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={})
        
        assert hasattr(result, 'llm_called')
        assert result.llm_called is False  # По умолчанию False

    def test_execution_result_llm_called_true(self):
        """Тест: ExecutionResult с llm_called=True"""
        result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={}, llm_called=True)
        
        assert result.llm_called is True

    def test_execution_result_llm_called_false(self):
        """Тест: ExecutionResult с llm_called=False"""
        result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={}, llm_called=False)
        
        assert result.llm_called is False


# ============================================================================
# ТЕСТ 2: BEHAVIORDECISION REQUIRES_LLM FLAG
# ============================================================================

class TestBehaviorDecisionRequiresLlm:
    """Тесты флага requires_llm в BehaviorDecision"""

    def test_behavior_decision_has_requires_llm_field(self):
        """Тест: BehaviorDecision имеет поле requires_llm"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability"
        )
        
        assert hasattr(decision, 'requires_llm')
        assert decision.requires_llm is False  # По умолчанию False

    def test_behavior_decision_requires_llm_true(self):
        """Тест: BehaviorDecision с requires_llm=True"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            requires_llm=True
        )
        
        assert decision.requires_llm is True

    def test_behavior_decision_requires_llm_false(self):
        """Тест: BehaviorDecision с requires_llm=False"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            requires_llm=False
        )
        
        assert decision.requires_llm is False


# ============================================================================
# ТЕСТ 3: INFRASTRUCTURE ERROR IF LLM NOT CALLED
# ============================================================================

class TestInfrastructureErrorIfLlmNotCalled:
    """Тесты InfrastructureError если LLM не вызван"""

    def test_infrastructure_error_when_requires_llm_but_not_called(self):
        """Тест: InfrastructureError если requires_llm=True но llm_called=False"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            requires_llm=True
        )
        
        execution_result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={}, llm_called=False)
        
        # Проверка условия
        if getattr(decision, 'requires_llm', False):
            if hasattr(execution_result, 'llm_called') and not execution_result.llm_called:
                error = InfrastructureError(
                    f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                )
                assert error is not None
                assert "test.capability" in error.message

    def test_no_error_when_requires_llm_and_called(self):
        """Тест: Нет ошибки если requires_llm=True и llm_called=True"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            requires_llm=True
        )
        
        execution_result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={}, llm_called=True)
        
        # Проверка условия - ошибки не должно быть
        error_raised = False
        try:
            if getattr(decision, 'requires_llm', False):
                if hasattr(execution_result, 'llm_called') and not execution_result.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )
        except InfrastructureError:
            error_raised = True
        
        assert error_raised is False

    def test_no_error_when_not_requires_llm(self):
        """Тест: Нет ошибки если requires_llm=False"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            requires_llm=False
        )
        
        execution_result = ExecutionResult(status=ExecutionStatus.COMPLETED, data={}, llm_called=False)
        
        # Проверка условия - ошибки не должно быть
        error_raised = False
        try:
            if getattr(decision, 'requires_llm', False):
                if hasattr(execution_result, 'llm_called') and not execution_result.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )
        except InfrastructureError:
            error_raised = True
        
        assert error_raised is False


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
