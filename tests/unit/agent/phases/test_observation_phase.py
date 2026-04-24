"""
Tests for refactored ObservationPhase and ObservationAnalysis.
Validates typed return values and observation history management.
"""
import pytest
from pydantic import ValidationError
from core.agent.state import AgentState, ObservationAnalysis


class TestObservationAnalysis:
    """Tests for ObservationAnalysis Pydantic model."""

    def test_create_valid_observation(self):
        """Test creating a valid ObservationAnalysis."""
        obs = ObservationAnalysis(
            status="success",
            insight="Data looks good",
            hint="Continue with current approach"
        )
        
        assert obs.status == "success"
        assert obs.insight == "Data looks good"
        assert obs.hint == "Continue with current approach"

    def test_observation_with_optional_fields(self):
        """Test ObservationAnalysis with optional fields."""
        obs = ObservationAnalysis(
            status="warning"
        )
        
        assert obs.status == "warning"
        assert obs.insight == ""
        assert obs.hint == ""

    def test_observation_serialization(self):
        """Test ObservationAnalysis serialization to dict."""
        obs = ObservationAnalysis(
            status="error",
            insight="Found issue",
            hint="Try alternative approach"
        )
        
        data = obs.model_dump()
        
        assert data['status'] == "error"
        assert data['insight'] == "Found issue"
        assert data['hint'] == "Try alternative approach"


class TestAgentStateObservationHistory:
    """Tests for AgentState observation_history management."""

    def test_push_observation_adds_to_history(self):
        """Test that observations are added to history."""
        state = AgentState()
        obs = ObservationAnalysis(
            status="success",
            insight="First observation"
        )
        
        state.push_observation(obs)
        
        assert len(state.observation_history) == 1
        assert state.observation_history[0].status == "success"

    def test_push_observation_respects_limit(self):
        """Test that observation history respects max limit of 3."""
        state = AgentState()
        
        # Add 4 observations
        for i in range(4):
            obs = ObservationAnalysis(
                status="success",
                insight=f"Observation {i}"
            )
            state.push_observation(obs)
        
        # Should only keep last 3
        assert len(state.observation_history) == 3
        assert state.observation_history[0].insight == "Observation 1"  # Oldest kept
        assert state.observation_history[2].insight == "Observation 3"  # Newest

    def test_push_observation_fifo_behavior(self):
        """Test FIFO behavior when exceeding limit."""
        state = AgentState()
        
        # Add 5 observations
        for i in range(5):
            obs = ObservationAnalysis(
                status="success",
                insight=f"Observation {i}"
            )
            state.push_observation(obs)
        
        # Should keep observations 2, 3, 4 (oldest removed first)
        assert len(state.observation_history) == 3
        assert state.observation_history[0].insight == "Observation 2"
        assert state.observation_history[1].insight == "Observation 3"
        assert state.observation_history[2].insight == "Observation 4"

    def test_empty_observation_history(self):
        """Test empty observation history."""
        state = AgentState()
        assert len(state.observation_history) == 0
        assert state.observation_history == []


class TestObservationPhaseTypedReturn:
    """Tests for ObservationPhase returning typed ObservationAnalysis."""

    @pytest.mark.asyncio
    async def test_analyze_returns_typed_result_rule_based(self, mocker):
        """Test that analyze() returns ObservationAnalysis in rule-based mode."""
        from core.agent.phases.observation_phase import ObservationPhase
        
        # Create mocks for dependencies with proper async support
        mock_observer = mocker.AsyncMock()
        mock_observer.analyze.return_value = {
            "status": "success",
            "insight": "Test insight",
            "hint": "Test hint"
        }
        
        mock_metrics = mocker.MagicMock()
        mock_policy = mocker.MagicMock()
        mock_log = mocker.MagicMock()
        mock_event_bus = mocker.MagicMock()
        
        phase = ObservationPhase(
            observer=mock_observer,
            metrics=mock_metrics,
            policy=mock_policy,
            log=mock_log,
            event_bus=mock_event_bus
        )
        
        # Mock ExecutionResult
        mock_result = mocker.MagicMock()
        mock_result.status.value = "success"
        mock_result.result_data = {"data": "sample"}
        mock_result.execution_time_ms = 100
        mock_result.data = {"data": "sample"}
        mock_result.error = None
        
        mock_session_context = mocker.MagicMock()
        mock_session_context.session_id = "test-session"
        
        result = await phase.analyze(
            result=mock_result,
            decision_action="test",
            decision_parameters={},
            session_context=mock_session_context,
            step_number=1
        )
        
        assert isinstance(result, ObservationAnalysis)
        assert result.status in ["success", "warning", "error", "unknown"]

    @pytest.mark.asyncio
    async def test_analyze_handles_empty_step_data(self, mocker):
        """Test analyze() handles empty step data gracefully."""
        from core.agent.phases.observation_phase import ObservationPhase
        
        mock_observer = mocker.AsyncMock()
        mock_observer.analyze.return_value = {
            "status": "success",
            "insight": "",
            "hint": ""
        }
        
        mock_metrics = mocker.MagicMock()
        mock_policy = mocker.MagicMock()
        mock_log = mocker.MagicMock()
        mock_event_bus = mocker.MagicMock()
        
        phase = ObservationPhase(
            observer=mock_observer,
            metrics=mock_metrics,
            policy=mock_policy,
            log=mock_log,
            event_bus=mock_event_bus
        )
        
        mock_result = mocker.MagicMock()
        mock_result.status.value = "success"
        mock_result.result_data = {}
        mock_result.execution_time_ms = 100
        mock_result.data = {}
        mock_result.error = None
        
        mock_session_context = mocker.MagicMock()
        mock_session_context.session_id = "test-session"
        
        result = await phase.analyze(
            result=mock_result,
            decision_action="test",
            decision_parameters={},
            session_context=mock_session_context,
            step_number=1
        )
        
        assert isinstance(result, ObservationAnalysis)
        assert result.status is not None

    @pytest.mark.asyncio
    async def test_analyze_handles_missing_context(self, mocker):
        """Test analyze() handles missing context gracefully."""
        from core.agent.phases.observation_phase import ObservationPhase
        
        mock_observer = mocker.AsyncMock()
        mock_observer.analyze.return_value = {
            "status": "success",
            "insight": "Test insight",
            "hint": "Test hint"
        }
        
        mock_metrics = mocker.MagicMock()
        mock_policy = mocker.MagicMock()
        mock_log = mocker.MagicMock()
        mock_event_bus = mocker.MagicMock()
        
        phase = ObservationPhase(
            observer=mock_observer,
            metrics=mock_metrics,
            policy=mock_policy,
            log=mock_log,
            event_bus=mock_event_bus
        )
        
        mock_result = mocker.MagicMock()
        mock_result.status.value = "success"
        mock_result.result_data = {"data": "sample"}
        mock_result.execution_time_ms = 100
        mock_result.data = {"data": "sample"}
        mock_result.error = None
        
        result = await phase.analyze(
            result=mock_result,
            decision_action="test",
            decision_parameters={},
            session_context=None,
            step_number=1
        )
        
        assert isinstance(result, ObservationAnalysis)
