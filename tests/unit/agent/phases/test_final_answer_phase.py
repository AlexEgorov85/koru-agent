"""
Тесты для FinalAnswerPhase.

Проверяемая бизнес-логика:
1. generate_final_answer() — генерирует финальный ответ через executor
2. generate_final_answer() — вызывает commit_turn() и sync_dialogue_callback()
3. generate_fallback_answer() — генерирует ответ при исчерпании лимита шагов
4. При ошибке генерации возвращает None (generate_final_answer) или fallback (generate_fallback_answer)
5. Извлечение final_answer из разных полей ответа (final_answer, answer)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.agent.phases.final_answer_phase import FinalAnswerPhase
from core.models.data.execution import ExecutionResult, ExecutionStatus


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def final_answer_phase():
    """FinalAnswerPhase с замоканными зависимостями."""
    mock_app_context = MagicMock()
    mock_executor = AsyncMock()
    mock_log = MagicMock()
    mock_event_bus = AsyncMock()
    
    phase = FinalAnswerPhase(
        application_context=mock_app_context,
        executor=mock_executor,
        agent_config=None,
        log=mock_log,
        event_bus=mock_event_bus,
    )
    return phase


@pytest.fixture
def mock_session_context():
    """Mock SessionContext."""
    ctx = MagicMock()
    ctx.session_id = "test-session"
    ctx.agent_id = "agent-001"
    ctx._max_steps = 10
    return ctx


@pytest.fixture
def mock_sync_callback():
    """Mock callback для синхронизации диалога."""
    return MagicMock()


@pytest.fixture
def success_final_answer_result():
    """Успешный результат генерации финального ответа."""
    result = MagicMock(spec=ExecutionResult)
    result.status = ExecutionStatus.COMPLETED
    result.data = {"final_answer": "Test answer", "confidence": 0.95}
    return result


# ============================================================================
# Тесты generate_final_answer()
# ============================================================================

class TestGenerateFinalAnswer:
    """Тесты генерации финального ответа."""
    
    @pytest.mark.asyncio
    async def test_calls_executor(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Вызывает executor.execute_action() для final_answer.generate."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning="Task completed",
            sync_dialogue_callback=mock_sync_callback,
        )
        
        final_answer_phase.executor.execute_action.assert_called_once()
        call_kwargs = final_answer_phase.executor.execute_action.call_args[1]
        assert call_kwargs["action_name"] == "final_answer.generate"
        assert "goal" in call_kwargs["parameters"]
    
    @pytest.mark.asyncio
    async def test_returns_execution_result(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Возвращает ExecutionResult при успехе."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        result = await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning="Task completed",
            sync_dialogue_callback=mock_sync_callback,
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_calls_commit_turn(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Вызывает session_context.commit_turn() с правильными параметрами."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning="Task completed",
            sync_dialogue_callback=mock_sync_callback,
        )
        
        mock_session_context.commit_turn.assert_called_once()
        call_kwargs = mock_session_context.commit_turn.call_args[1]
        assert call_kwargs["user_query"] == "Test goal"
        assert "Test answer" in call_kwargs["assistant_response"]
        assert "final_answer.generate" in call_kwargs["tools_used"]
    
    @pytest.mark.asyncio
    async def test_calls_sync_callback(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Вызывает sync_dialogue_callback() после commit_turn."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning="Task completed",
            sync_dialogue_callback=mock_sync_callback,
        )
        
        mock_sync_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extracts_final_answer_from_answer_field(
        self, final_answer_phase, mock_session_context, mock_sync_callback
    ):
        """Извлекает ответ из поля 'answer', если нет 'final_answer'."""
        result = MagicMock(spec=ExecutionResult)
        result.status = ExecutionStatus.COMPLETED
        result.data = {"answer": "Legacy answer"}
        
        final_answer_phase.executor.execute_action.return_value = result
        
        await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning=None,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        call_kwargs = mock_session_context.commit_turn.call_args[1]
        assert "Legacy answer" in call_kwargs["assistant_response"]
    
    @pytest.mark.asyncio
    async def test_returns_none_on_exception(
        self, final_answer_phase, mock_session_context, mock_sync_callback
    ):
        """Возвращает None при исключении."""
        final_answer_phase.executor.execute_action.side_effect = Exception("Generation failed")
        
        result = await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning=None,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_returns_none_on_failure_status(
        self, final_answer_phase, mock_session_context, mock_sync_callback
    ):
        """Возвращает None, если статус не COMPLETED."""
        result = MagicMock(spec=ExecutionResult)
        result.status = ExecutionStatus.FAILED
        result.data = None
        
        final_answer_phase.executor.execute_action.return_value = result
        
        result = await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            decision_reasoning=None,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        assert result is None


# ============================================================================
# Тесты generate_fallback_answer()
# ============================================================================

class TestGenerateFallbackAnswer:
    """Тесты генерации fallback-ответа."""
    
    @pytest.mark.asyncio
    async def test_calls_executor_with_fallback_flag(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Вызывает executor с is_fallback=True."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_fallback_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            executed_steps=5,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        call_kwargs = final_answer_phase.executor.execute_action.call_args[1]
        assert call_kwargs["parameters"]["is_fallback"] is True
        assert call_kwargs["parameters"]["executed_steps"] == 5
    
    @pytest.mark.asyncio
    async def test_returns_fallback_on_success(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Возвращает ExecutionResult при успешной генерации fallback."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        result = await final_answer_phase.generate_fallback_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            executed_steps=5,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_ultimate_fallback_on_error(
        self, final_answer_phase, mock_session_context, mock_sync_callback
    ):
        """При ошибке генерации возвращает ultimate fallback."""
        final_answer_phase.executor.execute_action.side_effect = Exception("Failed")
        
        result = await final_answer_phase.generate_fallback_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            executed_steps=5,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.FAILED
        assert "не удалось" in str(result.error).lower() or "шагов" in str(result.error)
        
        # Проверяем, что commit_turn все равно вызвался
        mock_session_context.commit_turn.assert_called()
    
    @pytest.mark.asyncio
    async def test_fallback_with_zero_steps(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Fallback с executed_steps=0 добавляет специфичное сообщение."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_fallback_answer(
            session_context=mock_session_context,
            session_id="test-session",
            agent_id="agent-001",
            goal="Test goal",
            executed_steps=0,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        call_kwargs = mock_session_context.commit_turn.call_args[1]
        assert "Действия не выполнялись" in call_kwargs["assistant_response"]


# ============================================================================
# Тесты интеграции с executor
# ============================================================================

class TestExecutorIntegration:
    """Тесты интеграции с ActionExecutor."""
    
    @pytest.mark.asyncio
    async def test_creates_execution_context(
        self, final_answer_phase, mock_session_context, mock_sync_callback, success_final_answer_result
    ):
        """Создает ExecutionContext с правильными параметрами."""
        final_answer_phase.executor.execute_action.return_value = success_final_answer_result
        
        await final_answer_phase.generate_final_answer(
            session_context=mock_session_context,
            session_id="sess-123",
            agent_id="agent-456",
            goal="Test",
            decision_reasoning=None,
            sync_dialogue_callback=mock_sync_callback,
        )
        
        call_kwargs = final_answer_phase.executor.execute_action.call_args[1]
        context = call_kwargs["context"]
        assert context.session_id == "sess-123"
        assert context.agent_id == "agent-456"
