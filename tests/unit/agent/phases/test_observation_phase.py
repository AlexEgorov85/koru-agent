"""
Тесты для ObservationPhase.

Проверяемая бизнес-логика:
1. analyze() возвращает типизированный ObservationAnalysis и НЕ мутирует состояние
2. decide_save_type() определяет тип сохранения на основе размера данных
3. _is_too_large() корректно оценивает лимиты (MAX_ROWS=5, MAX_JSON_BYTES=1500, MAX_TEXT_CHARS=1500)
4. get_size_info() возвращает корректную информацию о размере
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from core.agent.phases.observation_phase import ObservationPhase
from core.agent.state import ObservationAnalysis, AgentState
from core.models.data.execution import ExecutionResult, ExecutionStatus


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def real_agent_state():
    """Реальный AgentState для тестов."""
    return AgentState()


@pytest.fixture
def observation_phase():
    """ObservationPhase с замоканными зависимостями."""
    mock_observer = AsyncMock()
    mock_observer.analyze.return_value = {
        "status": "success",
        "insight": "Test insight",
        "hint": "Test hint",
        "quality": {},
        "_rule_based": False,
    }
    mock_metrics = MagicMock()
    mock_policy = MagicMock()
    mock_log = MagicMock()
    mock_event_bus = MagicMock()
    
    phase = ObservationPhase(
        observer=mock_observer,
        metrics=mock_metrics,
        policy=mock_policy,
        log=mock_log,
        event_bus=mock_event_bus,
    )
    return phase


@pytest.fixture
def mock_execution_result():
    """Mock объект с данными для ExecutionResult."""
    result = MagicMock()
    result.status = MagicMock(value="success")
    result.data = {"key": "value"}
    result.error = None
    return result


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
        """Пустой список → summary (слишком большой по логике _is_too_large)."""
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
    
    def test_explicit_mode_full(self):
        """explicit_mode='full' → raw_data (если данные помещаются)."""
        data = {"a": 1}
        assert ObservationPhase.decide_save_type(data, explicit_mode="full") == "raw_data"
    
    def test_explicit_mode_full_with_large_data(self):
        """explicit_mode='full' с большими данными → summary."""
        data = [{"id": i} for i in range(10)]
        assert ObservationPhase.decide_save_type(data, explicit_mode="full") == "summary"
    
    def test_explicit_mode_summary(self):
        """explicit_mode='summary' → summary независимо от данных."""
        data = {"a": 1}
        assert ObservationPhase.decide_save_type(data, explicit_mode="summary") == "summary"
    
    def test_none_data(self):
        """None данные → должно корректно обрабатываться."""
        # _is_too_large(None) вернет True (последняя строка метода)
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
    
    def test_large_dict_keys(self):
        """Dict с большим количеством ключей > MAX_DICT_KEYS=10."""
        data = {f"key{i}": i for i in range(15)}
        assert ObservationPhase._is_too_large(data)
    
    def test_none_data(self):
        """None считается слишком большим."""
        assert ObservationPhase._is_too_large(None)


class TestGetSizeInfo:
    """Тесты метода get_size_info()."""
    
    def test_list_info(self):
        """Информация о списке содержит row_count и json_size."""
        data = [{"id": 1}, {"id": 2}]
        info = ObservationPhase.get_size_info(data)
        assert info["type"] == "list"
        assert info["row_count"] == 2
        assert "json_size" in info
    
    def test_string_info(self):
        """Информация о строке содержит char_count."""
        data = "Hello World"
        info = ObservationPhase.get_size_info(data)
        assert info["type"] == "str"
        assert info["char_count"] == 11
    
    def test_dict_info(self):
        """Информация о dict содержит key_count."""
        data = {"a": 1, "b": 2}
        info = ObservationPhase.get_size_info(data)
        assert info["type"] == "dict"
        assert info["key_count"] == 2


# ============================================================================
# Тесты analyze() — основной метод фазы
# ============================================================================

class TestAnalyzeMethod:
    """Тесты метода analyze()."""
    
    @pytest.mark.asyncio
    async def test_returns_observation_analysis(self, observation_phase, mock_execution_result):
        """analyze() возвращает ObservationAnalysis."""
        result = await observation_phase.analyze(
            result=mock_execution_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(result, ObservationAnalysis)
    
    @pytest.mark.asyncio
    async def test_sets_save_type(self, observation_phase, mock_execution_result):
        """analyze() заполняет save_type в возвращаемом ObservationAnalysis."""
        result = await observation_phase.analyze(
            result=mock_execution_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert result.save_type in ("raw_data", "summary")
    
    @pytest.mark.asyncio
    async def test_does_not_mutate_state_with_none_context(self, observation_phase, mock_execution_result):
        """При session_context=None analyze() НЕ падает и не мутирует состояние."""
        result = await observation_phase.analyze(
            result=mock_execution_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(result, ObservationAnalysis)
    
    @pytest.mark.asyncio
    async def test_does_not_mutate_state_with_context(self, observation_phase, mock_execution_result):
        """analyze() НЕ вызывает методы agent_state (SRP: только анализ, без мутации)."""
        mock_session = MagicMock()
        mock_session.agent_state = MagicMock(spec=AgentState)
        
        await observation_phase.analyze(
            result=mock_execution_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session,
            step_number=1,
        )
        
        # Проверяем, что agent_state НЕ трогали
        mock_session.agent_state.push_observation.assert_not_called()
        mock_session.agent_state.add_step.assert_not_called()
        mock_session.agent_state.register_observation.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_calls_observer_analyze(self, observation_phase, mock_execution_result):
        """analyze() вызывает observer.analyze() для получения данных."""
        await observation_phase.analyze(
            result=mock_execution_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        observation_phase.observer.analyze.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_with_empty_data(self, observation_phase):
        """analyze() с пустыми данными (data=None)."""
        result = MagicMock(spec=ExecutionResult)
        result.status = MagicMock(value="success")
        result.data = None
        result.error = None
        
        obs = await observation_phase.analyze(
            result=result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert isinstance(obs, ObservationAnalysis)
        assert obs.save_type == "summary"  # None данные → summary
    
    @pytest.mark.asyncio
    async def test_with_large_data_sets_summary(self, observation_phase):
        """analyze() с большими данными устанавливает save_type='summary'."""
        result = MagicMock(spec=ExecutionResult)
        result.status = MagicMock(value="success")
        result.data = [{"id": i} for i in range(10)]  # > MAX_ROWS
        result.error = None
        
        obs = await observation_phase.analyze(
            result=result,
            decision_action="test_action",
            decision_parameters={},
            session_context=None,
            step_number=1,
        )
        assert obs.save_type == "summary"


# ============================================================================
# Тесты ObservationAnalysis модели
# ============================================================================

class TestObservationAnalysis:
    """Тесты Pydantic модели ObservationAnalysis."""
    
    def test_create_with_save_type(self):
        """ObservationAnalysis может быть создан с полем save_type."""
        obs = ObservationAnalysis(
            status="success",
            insight="Test",
            save_type="raw_data",
        )
        assert obs.save_type == "raw_data"
    
    def test_default_save_type_none(self):
        """save_type по умолчанию None."""
        obs = ObservationAnalysis(status="success")
        assert obs.save_type is None
    
    def test_serialization_includes_save_type(self):
        """При сериализации save_type включается в словарь."""
        obs = ObservationAnalysis(status="success", save_type="summary")
        data = obs.model_dump()
        assert "save_type" in data
        assert data["save_type"] == "summary"


# ============================================================================
# Тесты истории наблюдений (оставлено из старого файла)
# ============================================================================

class TestAgentStateObservationHistory:
    """Тесты управления историей наблюдений в AgentState."""
    
    def test_push_observation_adds_to_history(self):
        """Наблюдения добавляются в историю."""
        state = AgentState()
        obs = ObservationAnalysis(status="success", insight="First observation")
        state.push_observation(obs)
        assert len(state.observation_history) == 1
        assert state.observation_history[0].status == "success"
    
    def test_push_observation_respects_limit(self):
        """История наблюдений ограничена 3 записями."""
        state = AgentState()
        for i in range(4):
            obs = ObservationAnalysis(status="success", insight=f"Observation {i}")
            state.push_observation(obs)
        assert len(state.observation_history) == 3
        assert state.observation_history[0].insight == "Observation 1"
        assert state.observation_history[2].insight == "Observation 3"
    
    def test_fifo_behavior(self):
        """При превышении лимита старые записи удаляются (FIFO)."""
        state = AgentState()
        for i in range(5):
            obs = ObservationAnalysis(status="success", insight=f"Observation {i}")
            state.push_observation(obs)
        assert len(state.observation_history) == 3
        assert state.observation_history[0].insight == "Observation 2"
        assert state.observation_history[2].insight == "Observation 4"
    
    def test_empty_observation_history(self):
        """Пустая история наблюдений."""
        state = AgentState()
        assert len(state.observation_history) == 0
