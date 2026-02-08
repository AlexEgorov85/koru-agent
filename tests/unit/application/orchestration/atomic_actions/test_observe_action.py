"""
Unit tests for ObserveAction
"""
import pytest
from unittest.mock import Mock
from unittest.mock import AsyncMock
from domain.models.atomic_action.types import AtomicActionType
from application.orchestration.atomic_actions.react_actions import ObserveAction


class TestObserveAction:
    @pytest.mark.asyncio
    async def test_executes_observation_successfully(self):
        # Arrange
        mock_event_publisher = AsyncMock()
        action = ObserveAction(event_publisher=mock_event_publisher)
        
        # Act
        result = await action.execute({
            "action_result": "test result",
            "last_action": "test_action"
        })
        
        # Assert
        assert result.success is True
        assert result.action_type == AtomicActionType.OBSERVE
        assert "test_action" in result.observation
        assert result.processed_result == "test result"
    
    def test_validates_required_parameters(self):
        # Arrange
        action = ObserveAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.validate_parameters({}) is False
        assert action.validate_parameters({
            "action_result": "test",
            "last_action": "test"
        }) is True
    
    def test_requires_no_confirmation(self):
        # Arrange
        action = ObserveAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.requires_confirmation() is False
    
    @pytest.mark.asyncio
    async def test_rollback_returns_success(self):
        # Arrange
        action = ObserveAction(event_publisher=Mock())
        
        # Act
        result = await action.rollback("test_token")
        
        # Assert
        assert result.success is True
        assert result.action_type == AtomicActionType.OBSERVE
        assert result.can_rollback is False