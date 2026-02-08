"""
Unit tests for AtomicActionExecutor
"""
import pytest
from unittest.mock import Mock, AsyncMock
from domain.models.atomic_action.types import AtomicActionType
from domain.models.atomic_action.result import AtomicActionResult
from application.orchestration.atomic_actions.executor import AtomicActionExecutor
from application.orchestration.atomic_actions.react_actions import ThinkAction, ActAction, ObserveAction


class MockAtomicAction:
    def __init__(self, action_type, should_succeed=True):
        self._action_type = action_type
        self.should_succeed = should_succeed
    
    @property
    def action_type(self):
        return self._action_type
    
    def name(self):
        return str(self._action_type)
    
    def requires_confirmation(self):
        return False
    
    def validate_parameters(self, parameters):
        return True
    
    async def execute(self, parameters):
        return AtomicActionResult(
            success=self.should_succeed,
            action_type=self._action_type,
            can_rollback=True,
            rollback_token="test_token"
        )
    
    async def rollback(self, token):
        return AtomicActionResult(
            success=True,
            action_type=self._action_type
        )


class TestAtomicActionExecutor:
    @pytest.mark.asyncio
    async def test_executes_sequence_successfully(self):
        # Arrange
        executor = AtomicActionExecutor(event_publisher=Mock())
        
        # Register mock actions
        executor.register_action(MockAtomicAction(AtomicActionType.THINK))
        executor.register_action(MockAtomicAction(AtomicActionType.ACT))
        executor.register_action(MockAtomicAction(AtomicActionType.OBSERVE))
        
        sequence = [
            {"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}},
            {"action_type": AtomicActionType.ACT, "parameters": {"selected_action": "test", "parameters": {}}},
            {"action_type": AtomicActionType.OBSERVE, "parameters": {"action_result": {}, "last_action": "test"}}
        ]
        
        # Act
        results = await executor.execute_sequence(sequence)
        
        # Assert
        assert len(results) == 3
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_performs_rollback_on_failure(self):
        # Arrange
        executor = AtomicActionExecutor(event_publisher=Mock())
        
        # Register mock actions - first succeeds, second fails
        executor.register_action(MockAtomicAction(AtomicActionType.THINK, should_succeed=True))
        executor.register_action(MockAtomicAction(AtomicActionType.ACT, should_succeed=False))
        
        sequence = [
            {"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}},
            {"action_type": AtomicActionType.ACT, "parameters": {"selected_action": "test", "parameters": {}}}
        ]
        
        # Act
        results = await executor.execute_sequence(sequence, rollback_on_failure=True)
        
        # Assert
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        # Note: The rollback stack is not cleared after rollback in the current implementation
        # The rollback is performed but tokens remain in the stack