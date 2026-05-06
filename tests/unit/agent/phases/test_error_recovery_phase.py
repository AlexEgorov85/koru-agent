"""
Тесты для ErrorRecoveryPhase.

Проверяемая бизнес-логика:
1. handle_empty_sql_result() — диагностирует пустые результаты через sql_diagnostic_service
2. handle_empty_sql_result() — без service использует fallback (register_step_outcome)
3. handle_failed_execution() — классифицирует ошибки и возвращает диагностику
4. _classify_error() — определяет тип ошибки (syntax_error, timeout, semantic_empty, unknown)
5. При исключениях в диагностике не падает, использует fallback
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from core.agent.phases.error_recovery_phase import ErrorRecoveryPhase
from core.models.data.execution import ExecutionStatus


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def error_recovery_phase_with_service():
    """ErrorRecoveryPhase с sql_diagnostic_service."""
    mock_service = AsyncMock()
    mock_log = MagicMock()
    
    phase = ErrorRecoveryPhase(
        sql_diagnostic_service=mock_service,
        log=mock_log,
    )
    return phase


@pytest.fixture
def error_recovery_phase_without_service():
    """ErrorRecoveryPhase без sql_diagnostic_service."""
    mock_log = MagicMock()
    
    phase = ErrorRecoveryPhase(
        sql_diagnostic_service=None,
        log=mock_log,
    )
    return phase


@pytest.fixture
def mock_agent_state():
    """Mock AgentState для регистрации исходов."""
    state = MagicMock()
    return state


@pytest.fixture
def mock_session_context():
    """Mock SessionContext."""
    ctx = MagicMock()
    ctx.session_id = "test-session"
    return ctx


# ============================================================================
# Тесты handle_empty_sql_result()
# ============================================================================

class TestHandleEmptySqlResult:
    """Тесты обработки пустых SQL результатов."""
    
    @pytest.mark.asyncio
    async def test_calls_diagnostic_service(
        self, error_recovery_phase_with_service, mock_agent_state
    ):
        """Вызывает sql_diagnostic_service.diagnose_empty_result()."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_empty_result.return_value = {
            "diagnosis": "No data found",
            "suggestion": "Try different filters",
        }
        
        await phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={"query": "SELECT * FROM empty_table"},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        phase.sql_diagnostic_service.diagnose_empty_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_registers_with_diagnostic_info(
        self, error_recovery_phase_with_service, mock_agent_state
    ):
        """Регистрирует результат с диагностической информацией."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_empty_result.return_value = {
            "diagnosis": "Empty result",
            "suggestion": "Check filters",
        }
        
        await phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        # Проверяем, что register_step_outcome вызван с diagnostic
        mock_agent_state.register_step_outcome.assert_called_once()
        call_kwargs = mock_agent_state.register_step_outcome.call_args[1]
        assert "diagnostic" in call_kwargs["observation"]
    
    @pytest.mark.asyncio
    async def test_fallback_without_service(
        self, error_recovery_phase_without_service, mock_agent_state
    ):
        """Без service использует fallback регистрацию."""
        phase = error_recovery_phase_without_service
        
        await phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        # Должен вызвать register_step_outcome с базовой информацией
        mock_agent_state.register_step_outcome.assert_called_once()
        call_kwargs = mock_agent_state.register_step_outcome.call_args[1]
        assert call_kwargs["status"] == "empty"
        assert call_kwargs["observation"]["status"] == "empty"
    
    @pytest.mark.asyncio
    async def test_logs_diagnostic_result(
        self, error_recovery_phase_with_service, mock_agent_state
    ):
        """Логирует результат диагностики."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_empty_result.return_value = {
            "diagnosis": "Test diagnosis",
        }
        
        await phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        phase.log.info.assert_called()
        log_calls = [str(call) for call in phase.log.info.call_args_list]
        assert any("Diagnostic" in call for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_handles_diagnostic_exception(
        self, error_recovery_phase_with_service, mock_agent_state
    ):
        """При исключении в диагностике использует fallback."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_empty_result.side_effect = Exception("Diagnostic failed")
        
        # Не должно быть исключения
        await phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        # Должен вызваться fallback register_step_outcome
        mock_agent_state.register_step_outcome.assert_called()


# ============================================================================
# Тесты handle_failed_execution()
# ============================================================================

class TestHandleFailedExecution:
    """Тесты обработки неуспешного выполнения."""
    
    @pytest.mark.asyncio
    async def test_returns_none_without_service(self, error_recovery_phase_without_service):
        """Без service возвращает None."""
        phase = error_recovery_phase_without_service
        
        result = await phase.handle_failed_execution(
            decision_action="test_action",
            result_error="Some error",
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_returns_none_without_error(self, error_recovery_phase_with_service):
        """Без сообщения об ошибке возвращает None."""
        phase = error_recovery_phase_with_service
        
        result = await phase.handle_failed_execution(
            decision_action="test_action",
            result_error=None,
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_classifies_syntax_error(self, error_recovery_phase_with_service):
        """Классифицирует syntax error и возвращает рекомендации."""
        phase = error_recovery_phase_with_service
        
        result = await phase.handle_failed_execution(
            decision_action="sql_tool.execute",
            result_error="Syntax error near 'SELECT'",
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is not None
        assert result["error_type"] == "syntax_error"
        assert "suggestion" in result
        assert result["actionable"] is True
    
    @pytest.mark.asyncio
    async def test_classifies_timeout_error(self, error_recovery_phase_with_service):
        """Классифицирует timeout error."""
        phase = error_recovery_phase_with_service
        
        result = await phase.handle_failed_execution(
            decision_action="sql_tool.execute",
            result_error="Query timed out after 30 seconds",
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is not None
        assert result["error_type"] == "timeout"
        assert "LIMIT" in result["suggestion"] or "индекс" in result["suggestion"]
    
    @pytest.mark.asyncio
    async def test_classifies_semantic_empty(self, error_recovery_phase_with_service):
        """Классифицирует semantic empty и вызывает diagnostic service."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_semantic_empty.return_value = {
            "error_type": "semantic_empty",
            "diagnosis": "Query valid but empty",
        }
        
        result = await phase.handle_failed_execution(
            decision_action="sql_tool.execute",
            result_error="No results found",
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is not None
        assert result["error_type"] == "semantic_empty"
        phase.sql_diagnostic_service.diagnose_semantic_empty.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handles_unknown_error(self, error_recovery_phase_with_service):
        """Неизвестная ошибка возвращает тип 'unknown'."""
        phase = error_recovery_phase_with_service
        
        result = await phase.handle_failed_execution(
            decision_action="test_action",
            result_error="Some weird error that doesn't match any category",
            result_status=ExecutionStatus.FAILED,
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
        
        assert result is not None
        assert result["error_type"] == "unknown"
        assert result["actionable"] is False


# ============================================================================
# Тесты _classify_error()
# ============================================================================

class TestClassifyError:
    """Тесты классификации типов ошибок."""
    
    def test_syntax_error_variants(self, error_recovery_phase_without_service):
        """Различные варианты syntax error."""
        phase = error_recovery_phase_without_service
        
        assert phase._classify_error("Syntax error in SQL") == "syntax_error"
        assert phase._classify_error("Parse error near FROM") == "syntax_error"
        assert phase._classify_error("Invalid syntax") == "syntax_error"
        assert phase._classify_error("Unexpected token") == "syntax_error"
        assert phase._classify_error("SQL syntax error") == "syntax_error"
    
    def test_timeout_error_variants(self, error_recovery_phase_without_service):
        """Различные варианты timeout error."""
        phase = error_recovery_phase_without_service
        
        assert phase._classify_error("Query timed out") == "timeout"
        assert phase._classify_error("Timed out after 30s") == "timeout"
        assert phase._classify_error("Execution time exceeded") == "timeout"
        assert phase._classify_error("Query timeout limit reached") == "timeout"
    
    def test_semantic_empty_variants(self, error_recovery_phase_without_service):
        """Различные варианты semantic empty."""
        phase = error_recovery_phase_without_service
        
        assert phase._classify_error("No results found") == "semantic_empty"
        assert phase._classify_error("Empty result set") == "semantic_empty"
        assert phase._classify_error("No rows returned") == "semantic_empty"
        assert phase._classify_error("Zero matches") == "semantic_empty"
    
    def test_unknown_error(self, error_recovery_phase_without_service):
        """Неизвестная ошибка."""
        phase = error_recovery_phase_without_service
        
        assert phase._classify_error("Some random error") == "unknown"
        assert phase._classify_error("") == "unknown"
        assert phase._classify_error("Connection refused") == "unknown"


# ============================================================================
# Тесты устойчивости
# ============================================================================

class TestResilience:
    """Тесты устойчивости к ошибкам."""
    
    @pytest.mark.asyncio
    async def test_handle_empty_does_not_raise(
        self, error_recovery_phase_with_service, mock_agent_state
    ):
        """handle_empty_sql_result() не бросает исключения."""
        phase = error_recovery_phase_with_service
        phase.sql_diagnostic_service.diagnose_empty_result.side_effect = Exception("Boom")
        
        # Не должно быть исключения
        await phase.handle_empty_sql_result(
            decision_action="test",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_agent_state,
        )
    
    @pytest.mark.asyncio
    async def test_handle_failed_does_not_raise(
        self, error_recovery_phase_with_service
    ):
        """handle_failed_execution() не бросает исключения."""
        phase = error_recovery_phase_with_service
        
        # Даже с плохими входными данными не должно быть исключения
        result = await phase.handle_failed_execution(
            decision_action="test",
            result_error="Error",
            result_status=ExecutionStatus.FAILED,
            session_context=MagicMock(),
            agent_state=MagicMock(),
        )
        
        assert result is not None  # Должен вернуть диагностику, а не упасть
