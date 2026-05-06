"""
Тесты для ObservationPhase.

Проверяемая бизнес-логика:
1. analyze() возвращает ObservationResult (Pydantic модель)
2. decide_save_type() определяет тип сохранения на основе размера данных
3. _is_too_large() корректно оценивает лимиты (MAX_ROWS=5, MAX_JSON_BYTES=1500, MAX_TEXT_CHARS=1500)
4. Сжатие observation text при больших данных (row_count > 10)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.agent.phases.observation_phase import ObservationPhase
from core.agent.state import ObservationResult
from core.models.data.execution import ExecutionResult, ExecutionStatus


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def observation_phase():
    """ObservationPhase с замоканными зависимостями."""
    mock_metrics = MagicMock()
    mock_policy = MagicMock()
    mock_log = MagicMock()
    mock_event_bus = MagicMock()
    mock_app_context = MagicMock()
    mock_app_context.config.agent_defaults.observer_trigger_mode = "on_error"
    
    phase = ObservationPhase(
        metrics=mock_metrics,
        policy=mock_policy,
        log=mock_log,
        event_bus=mock_event_bus,
        application_context=mock_app_context,
    )
    return phase


@pytest.fixture
def mock_execution_result_success():
    """Успешный ExecutionResult с данными."""
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        data={"key": "value"},
        error=None,
    )


@pytest.fixture
def mock_execution_result_empty():
    """ExecutionResult с пустыми данными."""
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        data=[],
        error=None,
    )


@pytest.fixture
def mock_execution_result_error():
    """ExecutionResult с ошибкой."""
    return ExecutionResult(
        status=ExecutionStatus.FAILED,
        data=None,
        error=ValueError("Test error"),
    )


@pytest.fixture
def mock_execution_result_large_data():
    """ExecutionResult с большим набором данных."""
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        data=[{"id": i, "data": "x" * 100} for i in range(20)],
        error=None,
    )


# ============================================================================
# Тесты логики оценки размера данных (decide_save_type, _is_too_large)
# ============================================================================

class TestDecideSaveType:
    """Тесты метода decide_save_type()."""
    
    def test_small_list_returns_raw_data(self):
        """Список из 2 строк < MAX_ROWS=5 → raw_data."""
        data = [{"id": 1}, {"id": 2}]
        assert ObservationPhase.decide_save_type(data) == "raw_data"
    
    def test_large_list_returns_summary(self):
        """Список из 10 строк > MAX_ROWS=5 → summary."""
        data = [{"id": i} for i in range(10)]
        assert ObservationPhase.decide_save_type(data) == "summary"
    
    def test_empty_list_returns_summary(self):
        """Пустой список → summary."""
        assert ObservationPhase.decide_save_type([]) == "summary"
    
    def test_small_dict_returns_raw_data(self):
        """Маленький dict → raw_data."""
        data = {"a": 1, "b": 2}
        assert ObservationPhase.decide_save_type(data) == "raw_data"
    
    def test_large_json_dict_returns_summary(self):
        """Dict с большим JSON размером > MAX_JSON_BYTES=1500 → summary."""
        data = {"key": "x" * 2000}
        assert ObservationPhase.decide_save_type(data) == "summary"
    
    def test_small_string_returns_raw_data(self):
        """Короткая строка → raw_data."""
        data = "Hello"
        assert ObservationPhase.decide_save_type(data) == "raw_data"
    
    def test_large_string_returns_summary(self):
        """Длинная строка > MAX_TEXT_CHARS=1500 → summary."""
        data = "x" * 2000
        assert ObservationPhase.decide_save_type(data) == "summary"
    
    def test_none_data(self):
        """None данные → должно корректно обрабатываться."""
        assert ObservationPhase.decide_save_type(None) == "summary"


class TestIsTooLarge:
    """Тесты метода _is_too_large()."""
    
    def test_small_list(self):
        """Список из 3 элементов не слишком большой."""
        assert not ObservationPhase._is_too_large([1, 2, 3])
    
    def test_large_list(self):
        """Список из 10 элементов слишком большой."""
        assert ObservationPhase._is_too_large([i for i in range(10)])
    
    def test_empty_list(self):
        """Пустой список считается слишком большим."""
        assert ObservationPhase._is_too_large([])
    
    def test_small_string(self):
        """Короткая строка не слишком большая."""
        assert not ObservationPhase._is_too_large("hello")
    
    def test_large_string(self):
        """Длинная строка слишком большая."""
        assert ObservationPhase._is_too_large("x" * 2000)
    
    def test_small_dict(self):
        """Маленький dict не слишком большой."""
        assert not ObservationPhase._is_too_large({"a": 1})
    
    def test_none_data(self):
        """None считается слишком большим."""
        assert ObservationPhase._is_too_large(None)


# ============================================================================
# Тесты analyze() — основной метод фазы
# ============================================================================

class TestAnalyzeMethod:
    """Тесты метода analyze()."""
    
    @pytest.mark.asyncio
    async def test_returns_observation_result(self, observation_phase, mock_execution_result_success):
        """analyze() возвращает ObservationResult."""
        result = await observation_phase.analyze(
            result=mock_execution_result_success,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(result, ObservationResult)
    
    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, observation_phase, mock_execution_result_success):
        """ObservationResult содержит все обязательные поля."""
        result = await observation_phase.analyze(
            result=mock_execution_result_success,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert hasattr(result, 'status')
        assert hasattr(result, 'observation')
        assert hasattr(result, 'key_findings')
        assert hasattr(result, 'data_quality')
        assert hasattr(result, 'next_step_suggestion')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'requires_additional_action')
    
    @pytest.mark.asyncio
    async def test_with_empty_data(self, observation_phase, mock_execution_result_empty):
        """analyze() с пустыми данными корректно обрабатывает."""
        obs = await observation_phase.analyze(
            result=mock_execution_result_empty,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(obs, ObservationResult)
        assert obs.status == "empty"
    
    @pytest.mark.asyncio
    async def test_with_error_data(self, observation_phase, mock_execution_result_error):
        """analyze() с ошибкой корректно обрабатывает."""
        obs = await observation_phase.analyze(
            result=mock_execution_result_error,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(obs, ObservationResult)
        assert obs.status == "error"
    
    @pytest.mark.asyncio
    async def test_large_data_compression(self, observation_phase, mock_execution_result_large_data):
        """analyze() со большими данными сжимает observation text."""
        obs = await observation_phase.analyze(
            result=mock_execution_result_large_data,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(obs, ObservationResult)
        # Текст наблюдения должен быть сжат (не содержать все 20 строк)
        assert len(obs.observation) < 5000  # Разумный лимит для сжатого текста
        assert "summary" in obs.observation.lower() or "строк" in obs.observation


# ============================================================================
# Тесты ObservationResult модели
# ============================================================================

class TestObservationResult:
    """Тесты Pydantic модели ObservationResult."""
    
    def test_create_minimal(self):
        """ObservationResult может быть создан с минимальными полями."""
        obs = ObservationResult(status="success")
        assert obs.status == "success"
        assert obs.observation == ""
        assert obs.key_findings == []
        assert obs.errors == []
        assert obs.requires_additional_action == False
    
    def test_create_full(self):
        """ObservationResult может быть создан со всеми полями."""
        obs = ObservationResult(
            status="success",
            observation="Test observation",
            key_findings=["Finding 1"],
            data_quality={"completeness": 1.0},
            next_step_suggestion="Continue",
            errors=[],
            requires_additional_action=False,
        )
        assert obs.status == "success"
        assert obs.observation == "Test observation"
    
    def test_serialization(self):
        """При сериализации все поля включаются в словарь."""
        obs = ObservationResult(status="success", observation="Test")
        data = obs.model_dump()
        assert "status" in data
        assert "observation" in data
        assert "key_findings" in data
