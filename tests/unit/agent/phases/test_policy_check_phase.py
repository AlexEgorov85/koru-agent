"""
Тесты для PolicyCheckPhase.

Проверяемая бизнес-логика:
1. check_loop_conditions() проверяет метрики и возвращает (should_stop, reason)
2. validate_action() вызывает policy.evaluate() и возвращает True/False
3. handle_violation() логирует нарушение и регистрирует заблокированное действие
4. Проверка token budget и сжатия контекста (Фаза 3)
5. Fail-Fast: при нарушении выбрасывается PolicyViolationError
"""

import pytest
from unittest.mock import MagicMock, patch
from core.agent.phases.policy_check_phase import PolicyCheckPhase
from core.agent.components.policy import AgentPolicy, PolicyViolationError
from core.session_context.session_context import SessionContext


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def policy_check_phase():
    """PolicyCheckPhase с замоканными зависимостями."""
    mock_policy = MagicMock(spec=AgentPolicy)
    mock_log = MagicMock()
    mock_event_bus = MagicMock()
    
    phase = PolicyCheckPhase(
        policy=mock_policy,
        log=mock_log,
        event_bus=mock_event_bus,
    )
    return phase


@pytest.fixture
def mock_metrics():
    """Mock AgentMetrics с should_stop=False по умолчанию."""
    metrics = MagicMock()
    metrics.should_stop.return_value = (False, None)
    metrics.total_tokens_used = 100
    return metrics


@pytest.fixture
def mock_session_context():
    """Реальный SessionContext для тестов."""
    ctx = MagicMock(spec=SessionContext)
    ctx.session_id = "test-session"
    ctx.agent_id = "agent-001"
    ctx.agent_state = MagicMock()
    ctx.agent_state.consecutive_repeated_actions = 0
    ctx.agent_state.consecutive_empty_results = 0
    ctx.get_context_token_estimate.return_value = 500
    return ctx


# ============================================================================
# Тесты check_loop_conditions()
# ============================================================================

class TestCheckLoopConditions:
    """Тесты проверки условий остановки."""
    
    def test_returns_false_when_no_conditions(self, policy_check_phase, mock_metrics, mock_session_context):
        """Нет условий для остановки → (False, None)."""
        should_stop, reason = policy_check_phase.check_loop_conditions(
            session_context=mock_session_context,
            metrics=mock_metrics,
            step_number=1,
        )
        
        assert should_stop is False
        assert reason is None
    
    def test_returns_true_when_metrics_stop(self, policy_check_phase, mock_metrics, mock_session_context):
        """Метрики сигнализируют остановку → (True, reason)."""
        mock_metrics.should_stop.return_value = (True, "Max steps exceeded")
        
        should_stop, reason = policy_check_phase.check_loop_conditions(
            session_context=mock_session_context,
            metrics=mock_metrics,
            step_number=10,
        )
        
        assert should_stop is True
        assert reason == "Max steps exceeded"
    
    def test_token_budget_exceeded(self, policy_check_phase, mock_metrics, mock_session_context):
        """Превышение token budget → (True, reason)."""
        mock_metrics.total_tokens_used = 10000
        agent_config = MagicMock()
        agent_config.max_total_tokens = 5000
        
        should_stop, reason = policy_check_phase.check_loop_conditions(
            session_context=mock_session_context,
            metrics=mock_metrics,
            step_number=5,
            agent_config=agent_config,
        )
        
        assert should_stop is True
        assert "Token budget" in reason
    
    def test_context_compression_called(self, policy_check_phase, mock_metrics, mock_session_context):
        """Превышение context_token_threshold → вызывается compress_history."""
        agent_config = MagicMock()
        agent_config.context_token_threshold = 1000
        mock_session_context.get_context_token_estimate.return_value = 1500
        
        with patch.object(mock_session_context, 'compress_history', return_value=(1500, 800)) as mock_compress:
            should_stop, reason = policy_check_phase.check_loop_conditions(
                session_context=mock_session_context,
                metrics=mock_metrics,
                step_number=5,
                agent_config=agent_config,
            )
            
            mock_compress.assert_called_once_with(max_tokens=1000, preserve_last_n=5)
        
        assert should_stop is False  # Сжатие не останавливает цикл
    
    def test_no_stop_after_compression(self, policy_check_phase, mock_metrics, mock_session_context):
        """После сжатия контекста цикл продолжается."""
        agent_config = MagicMock()
        agent_config.context_token_threshold = 1000
        mock_session_context.get_context_token_estimate.return_value = 1500
        
        should_stop, reason = policy_check_phase.check_loop_conditions(
            session_context=mock_session_context,
            metrics=mock_metrics,
            step_number=5,
            agent_config=agent_config,
        )
        
        assert should_stop is False


# ============================================================================
# Тесты validate_action()
# ============================================================================

class TestValidateAction:
    """Тесты валидации действия через политику."""
    
    def test_returns_true_when_policy_allows(self, policy_check_phase, mock_metrics, mock_session_context):
        """Policy разрешает действие → True."""
        policy_check_phase.policy.evaluate.return_value = None  # Нет исключения
        
        result = policy_check_phase.validate_action(
            action_name="sql_tool.execute",
            metrics=mock_metrics,
            session_context=mock_session_context,
            parameters={"query": "SELECT 1"},
        )
        
        assert result is True
    
    def test_calls_policy_evaluate(self, policy_check_phase, mock_metrics, mock_session_context):
        """validate_action() вызывает policy.evaluate() с правильными параметрами."""
        policy_check_phase.policy.evaluate.return_value = None
        
        policy_check_phase.validate_action(
            action_name="sql_tool.execute",
            metrics=mock_metrics,
            session_context=mock_session_context,
            parameters={"query": "SELECT 1"},
        )
        
        policy_check_phase.policy.evaluate.assert_called_once()
        call_kwargs = policy_check_phase.policy.evaluate.call_args[1]
        assert call_kwargs["action_name"] == "sql_tool.execute"
        assert "consecutive_repeated_actions" in call_kwargs["state_data"]
    
    def test_raises_policy_violation(self, policy_check_phase, mock_metrics, mock_session_context):
        """Policy выбрасывает PolicyViolationError → тест должен проверить это."""
        from core.agent.components.policy import PolicyViolation
        
        # Настраиваем мок для выброса исключения
        violation = PolicyViolation(
            allowed=False,
            violations=["repeated_actions"],
        )
        policy_check_phase.policy.evaluate.side_effect = PolicyViolationError(violation)
        
        with pytest.raises(PolicyViolationError):
            policy_check_phase.validate_action(
                action_name="sql_tool.execute",
                metrics=mock_metrics,
                session_context=mock_session_context,
            )
        policy_check_phase.policy.evaluate.side_effect = PolicyViolationError(violation)
        
        with pytest.raises(PolicyViolationError):
            policy_check_phase.validate_action(
                action_name="sql_tool.execute",
                metrics=mock_metrics,
                session_context=mock_session_context,
            )
        
        with pytest.raises(PolicyViolationError):
            policy_check_phase.validate_action(
                action_name="sql_tool.execute",
                metrics=mock_metrics,
                session_context=mock_session_context,
            )
    
    def test_passes_consecutive_counts(self, policy_check_phase, mock_metrics, mock_session_context):
        """Передает consecutive_метрики из agent_state в policy.evaluate."""
        policy_check_phase.policy.evaluate.return_value = None
        
        # Настраиваем мок agent_state
        mock_session_context.agent_state.consecutive_repeated_actions = 3
        mock_session_context.agent_state.consecutive_empty_results = 2
        
        policy_check_phase.validate_action(
            action_name="test",
            metrics=mock_metrics,
            session_context=mock_session_context,
        )
        
        call_kwargs = policy_check_phase.policy.evaluate.call_args[1]
        assert call_kwargs["state_data"]["consecutive_repeated_actions"] == 3
        assert call_kwargs["state_data"]["consecutive_empty_results"] == 2


# ============================================================================
# Тесты handle_violation()
# ============================================================================

class TestHandleViolation:
    """Тесты обработки нарушений политики."""
    
    def test_logs_warning(self, policy_check_phase):
        """handle_violation() логирует предупреждение."""
        from core.agent.components.policy import PolicyViolation
        
        violation = PolicyViolation(
            allowed=False,
            violations=["test_violation"],
        )
        error = PolicyViolationError(violation)
        
        policy_check_phase.handle_violation(
            error=error,
            decision_action="test_action",
            step_number=1,
            session_context=MagicMock(),
        )
        
        policy_check_phase.log.warning.assert_called_once()
    
    def test_registers_blocked_action(self, policy_check_phase):
        """Регистрирует заблокированное действие в agent_state."""
        from core.agent.components.policy import PolicyViolation
        
        violation = PolicyViolation(
            allowed=False,
            violations=["test_violation"],
        )
        error = PolicyViolationError(violation)
        
        mock_session = MagicMock()
        
        policy_check_phase.handle_violation(
            error=error,
            decision_action="test_action",
            step_number=1,
            session_context=mock_session,
        )
        
        # Проверяем, что register_step_outcome вызван
        mock_session.agent_state.register_step_outcome.assert_called_once()
    
    def test_registers_step_in_context(self, policy_check_phase):
        """Регистрирует шаг в session_context."""
        from core.agent.components.policy import PolicyViolation
        
        violation = PolicyViolation(
            allowed=False,
            violations=["test_violation"],
        )
        error = PolicyViolationError(violation)
        
        mock_session = MagicMock()
        
        policy_check_phase.handle_violation(
            error=error,
            decision_action="test_action",
            step_number=1,
            session_context=mock_session,
        )
        
        # Проверяем, что register_step вызван
        mock_session.register_step.assert_called_once()
    
    def test_returns_policy_message(self, policy_check_phase):
        """Возвращает строку с сообщением о нарушении."""
        from core.agent.components.policy import PolicyViolation
        
        violation = PolicyViolation(
            allowed=False,
            violations=["test_violation"],
        )
        error = PolicyViolationError(violation)
        
        result = policy_check_phase.handle_violation(
            error=error,
            decision_action="test_action",
            step_number=1,
            session_context=MagicMock(),
        )
        
        assert isinstance(result, str)
        assert "POLICY_BLOCKED" in result or "violation" in result.lower()
