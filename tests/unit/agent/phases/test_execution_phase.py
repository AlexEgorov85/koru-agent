"""
Тесты для ExecutionPhase.

Проверяемая бизнес-логика:
1. execute() вызывает SafeExecutor.execute() или execute_with_config()
2. Обрабатывает успешное выполнение и ошибки
3. Логирует результаты (TOOL_CALL, TOOL_RESULT, TOOL_ERROR)
4. Публикует событие ACTION_PERFORMED в event_bus
5. При исключении возвращает ExecutionResult.failure()
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from core.agent.phases.execution_phase import ExecutionPhase
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.components.action_executor import ExecutionContext


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def execution_phase():
    """ExecutionPhase с замоканными зависимостями."""
    mock_safe_executor = AsyncMock()
    mock_log = MagicMock()
    mock_event_bus = AsyncMock()
    
    phase = ExecutionPhase(
        safe_executor=mock_safe_executor,
        log=mock_log,
        event_bus=mock_event_bus,
    )
    return phase


@pytest.fixture
def mock_success_result():
    """Успешный ExecutionResult."""
    return ExecutionResult.success(data={"result": "test data"})


@pytest.fixture
def mock_failure_result():
    """Неуспешный ExecutionResult."""
    return ExecutionResult.failure(error="Test error")


# ============================================================================
# Тесты execute()
# ============================================================================

class TestExecute:
    """Тесты основного метода execute()."""
    
    @pytest.mark.asyncio
    async def test_calls_safe_executor_execute(self, execution_phase, mock_success_result):
        """execute() вызывает safe_executor.execute() без конфига."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        result = await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={"param": "value"},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.safe_executor.execute.assert_called_once()
        call_kwargs = execution_phase.safe_executor.execute.call_args[1]
        assert call_kwargs["capability_name"] == "test_tool.execute"
        assert call_kwargs["parameters"] == {"param": "value"}
    
    @pytest.mark.asyncio
    async def test_calls_execute_with_config(self, execution_phase, mock_success_result):
        """execute() вызывает execute_with_config() при наличии step_config."""
        execution_phase.safe_executor.execute_with_config.return_value = mock_success_result
        execution_phase.agent_config = MagicMock()
        execution_phase.agent_config.steps = {"step_1": MagicMock(capability="test_tool.execute")}
        
        result = await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={"param": "value"},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.safe_executor.execute_with_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_returns_execution_result(self, execution_phase, mock_success_result):
        """execute() возвращает ExecutionResult."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        result = await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_logs_tool_call(self, execution_phase, mock_success_result):
        """execute() логирует вызов инструмента."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={"query": "SELECT 1"},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.log.info.assert_called()
        # Проверяем наличие лога о запуске
        log_calls = [str(call) for call in execution_phase.log.info.call_args_list]
        assert any("Запускаю" in call for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_logs_success(self, execution_phase, mock_success_result):
        """execute() логирует успешное выполнение."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        # Проверяем лог об успехе
        log_calls = [str(call) for call in execution_phase.log.info.call_args_list]
        assert any("выполнено" in call or "✅" in call for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_logs_failure(self, execution_phase, mock_failure_result):
        """execute() логирует ошибку при неуспешном выполнении."""
        execution_phase.safe_executor.execute.return_value = mock_failure_result
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.log.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_publishes_event_on_success(self, execution_phase, mock_success_result):
        """execute() публикует ACTION_PERFORMED при успехе."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.event_bus.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publishes_event_on_failure(self, execution_phase, mock_failure_result):
        """execute() публикует ACTION_PERFORMED даже при ошибке."""
        execution_phase.safe_executor.execute.return_value = mock_failure_result
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        execution_phase.event_bus.publish.assert_called_once()
        # Проверяем, что статус в событии - FAILED
        call_args = execution_phase.event_bus.publish.call_args
        event_data = call_args[0][1]
        assert event_data["status"] == ExecutionStatus.FAILED.value
    
    @pytest.mark.asyncio
    async def test_handles_exception(self, execution_phase):
        """execute() обрабатывает исключения и возвращает failure."""
        execution_phase.safe_executor.execute.side_effect = Exception("Unexpected error")
        
        result = await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=MagicMock(),
            session_id="test-session",
            agent_id="agent-001",
            step_number=1,
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert "Unexpected error" in str(result.error)
    
    @pytest.mark.asyncio
    async def test_creates_execution_context(self, execution_phase, mock_success_result):
        """execute() создает ExecutionContext с правильными параметрами."""
        execution_phase.safe_executor.execute.return_value = mock_success_result
        
        mock_session = MagicMock()
        
        await execution_phase.execute(
            decision_action="test_tool.execute",
            decision_parameters={},
            session_context=mock_session,
            session_id="sess-123",
            agent_id="agent-456",
            step_number=5,
        )
        
        # Проверяем, что ExecutionContext создан с правильными параметрами
        call_kwargs = execution_phase.safe_executor.execute.call_args[1]
        context = call_kwargs["context"]
        assert isinstance(context, ExecutionContext)
        assert context.session_id == "sess-123"
        assert context.agent_id == "agent-456"
