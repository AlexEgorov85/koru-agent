"""
Тесты для DecisionPhase.

Проверяемая бизнес-логика:
1. execute() вызывает pattern.decide() с правильными параметрами
2. Возвращает объект Decision
3. Логирует этапы через log.info с event_type
4. Публикует событие CAPABILITY_SELECTED в event_bus
5. Фаза только для чтения — не мутирует состояние
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, call
from core.agent.phases.decision_phase import DecisionPhase
from core.agent.behaviors.base import Decision, DecisionType


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def decision_phase():
    """DecisionPhase с замоканными зависимостями."""
    mock_log = MagicMock()
    mock_event_bus = AsyncMock()
    phase = DecisionPhase(log=mock_log, event_bus=mock_event_bus)
    return phase


@pytest.fixture
def mock_pattern():
    """Mock паттерна с возвращаемым Decision."""
    pattern = AsyncMock()
    pattern.decide.return_value = Decision(
        type=DecisionType.ACT,
        action="test_tool.execute",
        reasoning="Test reasoning",
    )
    return pattern


@pytest.fixture
def mock_session_context():
    """Mock SessionContext."""
    ctx = MagicMock()
    ctx.session_id = "test-session-123"
    ctx.agent_id = "agent-001"
    return ctx


# ============================================================================
# Тесты execute()
# ============================================================================

class TestExecute:
    """Тесты основного метода execute()."""
    
    @pytest.mark.asyncio
    async def test_calls_pattern_decide(self, decision_phase, mock_pattern, mock_session_context):
        """execute() вызывает pattern.decide() с session_context и capabilities."""
        await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=["tool1", "tool2"],
            step_number=1,
        )
        
        mock_pattern.decide.assert_called_once_with(
            session_context=mock_session_context,
            available_capabilities=["tool1", "tool2"],
        )
    
    @pytest.mark.asyncio
    async def test_returns_decision(self, decision_phase, mock_pattern, mock_session_context):
        """execute() возвращает объект Decision."""
        result = await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=1,
        )
        
        assert isinstance(result, Decision)
        assert result.type == DecisionType.ACT
        assert result.action == "test_tool.execute"
    
    @pytest.mark.asyncio
    async def test_logs_decision(self, decision_phase, mock_pattern, mock_session_context):
        """execute() логирует этапы принятия решения."""
        await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=1,
        )
        
        # Проверяем, что логирование вызывалось
        decision_phase.log.info.assert_called()
        # Проверяем наличие ключевых сообщений
        log_calls = [str(call) for call in decision_phase.log.info.call_args_list]
        assert any("Pattern.decide()" in call for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_publishes_event(self, decision_phase, mock_pattern, mock_session_context):
        """execute() публикует событие CAPABILITY_SELECTED."""
        await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=1,
        )
        
        decision_phase.event_bus.publish.assert_called_once()
        # Проверяем тип события
        call_args = decision_phase.event_bus.publish.call_args
        assert call_args[0][0] == "CAPABILITY_SELECTED" or "CAPABILITY_SELECTED" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_with_finish_decision(self, decision_phase, mock_session_context):
        """execute() корректно обрабатывает FINISH решение."""
        finish_pattern = AsyncMock()
        finish_pattern.decide.return_value = Decision(
            type=DecisionType.FINISH,
            action=None,
            reasoning="Task completed",
        )
        
        result = await decision_phase.execute(
            pattern=finish_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=5,
        )
        
        assert result.type == DecisionType.FINISH
        assert result.action is None
    
    @pytest.mark.asyncio
    async def test_with_empty_capabilities(self, decision_phase, mock_pattern, mock_session_context):
        """execute() работает с пустым списком capabilities."""
        result = await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=1,
        )
        
        assert isinstance(result, Decision)
        # Pattern должен получить пустой список
        call_args = mock_pattern.decide.call_args
        assert call_args[1]["available_capabilities"] == []
    
    @pytest.mark.asyncio
    async def test_step_number_for_logging(self, decision_phase, mock_pattern, mock_session_context):
        """execute() передает step_number в логи (проверка через publish)."""
        await decision_phase.execute(
            pattern=mock_pattern,
            session_context=mock_session_context,
            available_capabilities=[],
            step_number=42,
        )
        
        # Проверяем, что step передан в event
        call_args = decision_phase.event_bus.publish.call_args
        event_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('data', {})
        assert event_data.get('step') == 42 or event_data.get('step_number') == 42
