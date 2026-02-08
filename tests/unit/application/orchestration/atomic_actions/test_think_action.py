"""
Unit tests for ThinkAction
"""
import pytest
from unittest.mock import Mock
from unittest.mock import AsyncMock
from domain.models.atomic_action.types import AtomicActionType
from application.orchestration.atomic_actions.react_actions import ThinkAction


class TestThinkAction:
    @pytest.mark.asyncio
    async def test_executes_chain_of_thought(self):
        # Arrange
        mock_event_publisher = AsyncMock()
        action = ThinkAction(event_publisher=mock_event_publisher)
        
        # Act
        result = await action.execute({"goal": "Проанализировать код"})
        
        # Assert
        assert result.success is True
        assert len(result.thought) > 0
        assert result.action_type == AtomicActionType.THINK
    
    def test_validates_required_parameters(self):
        # Arrange
        action = ThinkAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.validate_parameters({}) is False
        assert action.validate_parameters({"goal": "test"}) is True
    
    def test_requires_no_confirmation(self):
        # Arrange
        action = ThinkAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.requires_confirmation() is False
    
    @pytest.mark.asyncio
    async def test_rollback_returns_success(self):
        # Arrange
        action = ThinkAction(event_publisher=Mock())
        
        # Act
        result = await action.rollback("test_token")
        
        # Assert
        assert result.success is True
        assert result.action_type == AtomicActionType.THINK
        assert result.can_rollback is False