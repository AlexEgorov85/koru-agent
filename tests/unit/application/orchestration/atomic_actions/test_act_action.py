"""
Unit tests for ActAction
"""
import pytest
from unittest.mock import Mock
from unittest.mock import AsyncMock
from domain.models.atomic_action.types import AtomicActionType
from application.orchestration.atomic_actions.react_actions import ActAction


class TestActAction:
    @pytest.mark.asyncio
    async def test_executes_action_successfully(self):
        # Arrange
        mock_event_publisher = AsyncMock()
        action = ActAction(event_publisher=mock_event_publisher)
        
        # Act
        result = await action.execute({
            "selected_action": "test_action",
            "action_parameters": {},
            "available_capabilities": ["test_action"]
        })
        
        # Assert
        assert result.success is True
        assert result.action_type == AtomicActionType.ACT
        assert result.executed_action == "test_action"
        assert result.can_rollback is True
    
    @pytest.mark.asyncio
    async def test_fails_when_action_not_available(self):
        # Arrange
        mock_event_publisher = AsyncMock()
        action = ActAction(event_publisher=mock_event_publisher)
        
        # Act
        result = await action.execute({
            "selected_action": "nonexistent_action",
            "action_parameters": {},
            "available_capabilities": ["other_action"]
        })
        
        # Assert
        assert result.success is False
        assert "недоступно" in result.error_message.lower()
    
    def test_validates_required_parameters(self):
        # Arrange
        action = ActAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.validate_parameters({}) is False
        assert action.validate_parameters({"selected_action": "test"}) is True
    
    def test_requires_confirmation(self):
        # Arrange
        action = ActAction(event_publisher=Mock())
        
        # Act & Assert
        assert action.requires_confirmation() is True
    
    @pytest.mark.asyncio
    async def test_rollback_returns_success(self):
        # Arrange
        action = ActAction(event_publisher=Mock())
        
        # Act
        result = await action.rollback("test_token")
        
        # Assert
        assert result.success is True
        assert result.action_type == AtomicActionType.ACT
        assert result.can_rollback is False