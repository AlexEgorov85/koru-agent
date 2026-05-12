"""
Unit-тесты для оркестрации DataAnalysisSkill:
- _select_strategies (auto mode, mode override)
- _normalize_parameters
- _normalize_to_rows
- _execute_with_fallback
- _get_step_data
- _save_result_to_context
- _get_session_context
"""
from unittest.mock import AsyncMock, MagicMock, ANY
import pytest

from core.components.skills.data_analysis.skill import DataAnalysisSkill
from core.components.skills.data_analysis.base_strategy import AnalysisInput, AnalysisResult, AbstractStrategy


# ============================================================================
# helpers
# ============================================================================

class FakeStrategy(AbstractStrategy):
    """Стратегия-заглушка для тестов _select_strategies."""

    def __init__(self, name, skill, can_handle_result=True, execute_result=None):
        super().__init__(skill)
        self._name = name
        self._can_handle_result = can_handle_result
        self._execute_result = execute_result or AnalysisResult(answer=f"result_{name}", confidence=0.5)

    @property
    def name(self):
        return self._name

    def can_handle(self, data, question):
        return self._can_handle_result

    async def execute(self, input_data):
        return self._execute_result


def make_skill(strategies=None):
    skill = DataAnalysisSkill(
        name="data_analysis",
        component_config=MagicMock(),
        executor=MagicMock(),
        application_context=None,
    )
    if strategies is not None:
        skill._strategies = strategies
    return skill


# ============================================================================
# _select_strategies
# ============================================================================

class TestSelectStrategies:

    def test_auto_picks_can_handle_true(self):
        s1 = FakeStrategy("s1", None, can_handle_result=True)
        s2 = FakeStrategy("s2", None, can_handle_result=False)
        skill = make_skill(strategies=[s1, s2])
        result = skill._select_strategies([{"a": 1}], "вопрос", mode_override=None)
        assert result == [s1]

    def test_auto_fallback_when_none_match(self):
        s1 = FakeStrategy("s1", None, can_handle_result=False)
        s2 = FakeStrategy("s2", None, can_handle_result=False)
        skill = make_skill(strategies=[s1, s2])
        result = skill._select_strategies([{"a": 1}], "вопрос", mode_override=None)
        assert result == [s2]  # last strategy as fallback

    def test_mode_override_selects_correct(self):
        s1 = FakeStrategy("python", None)
        s2 = FakeStrategy("llm", None)
        s3 = FakeStrategy("mapreduce", None)
        skill = make_skill(strategies=[s1, s2, s3])
        result = skill._select_strategies([{"a": 1}], "вопрос", mode_override="llm")
        assert result == [s2]

    def test_unknown_mode_raises(self):
        skill = make_skill()
        with pytest.raises(ValueError, match="Неизвестный режим"):
            skill._select_strategies([{"a": 1}], "вопрос", mode_override="nonexistent")


# ============================================================================
# _normalize_parameters
# ============================================================================

class TestNormalizeParameters:

    def test_dict_passthrough(self):
        skill = make_skill()
        result = skill._normalize_parameters({"question": "q", "step_id": 1})
        assert result == {"question": "q", "step_id": 1}

    def test_pydantic_model(self):
        skill = make_skill()

        class FakeModel:
            def model_dump(self):
                return {"question": "q", "step_id": 1}

        result = skill._normalize_parameters(FakeModel())
        assert result == {"question": "q", "step_id": 1}

    def test_unsupported_type_raises(self):
        skill = make_skill()
        with pytest.raises(ValueError, match="Неподдерживаемый тип"):
            skill._normalize_parameters("string")


# ============================================================================
# _normalize_to_rows
# ============================================================================

class TestNormalizeToRows:

    def test_list_of_dicts_passthrough(self):
        skill = make_skill()
        data = [{"id": 1, "name": "test"}]
        result = skill._normalize_to_rows(data)
        assert result == data

    def test_dict_with_rows_key(self):
        skill = make_skill()
        data = {"rows": [{"id": 1}]}
        result = skill._normalize_to_rows(data)
        assert result == [{"id": 1}]

    def test_dict_with_data_key(self):
        skill = make_skill()
        data = {"data": [{"id": 1}]}
        result = skill._normalize_to_rows(data)
        assert result == [{"id": 1}]

    def test_plain_dict_wraps_in_list(self):
        skill = make_skill()
        data = {"id": 1}
        result = skill._normalize_to_rows(data)
        assert result == [{"id": 1}]

    def test_string_wraps_as_text(self):
        skill = make_skill()
        result = skill._normalize_to_rows("hello world")
        assert result == [{"text": "hello world"}]

    def test_list_of_non_dicts_passthrough(self):
        skill = make_skill()
        data = ["row1", "row2"]
        result = skill._normalize_to_rows(data)
        assert result == data

    def test_none_wraps_as_content(self):
        skill = make_skill()
        result = skill._normalize_to_rows(None)
        assert result == [{"content": "None"}]


# ============================================================================
# _execute_with_fallback
# ============================================================================

class TestExecuteWithFallback:

    @pytest.mark.asyncio
    async def test_first_strategy_succeeds(self):
        s1 = FakeStrategy("s1", None, execute_result=AnalysisResult(answer="ok", confidence=0.9))
        s2 = FakeStrategy("s2", None)
        skill = make_skill(strategies=[s1, s2])
        result = await skill._execute_with_fallback(
            [s1, s2],
            AnalysisInput(data=[], question="q", step_id=1, execution_context=MagicMock()),
        )
        assert result.answer == "ok"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        s1 = FakeStrategy("s1", None, execute_result=AnalysisResult(answer="", error="fail"))
        s2 = FakeStrategy("s2", None, execute_result=AnalysisResult(answer="fallback ok", confidence=0.7))
        skill = make_skill(strategies=[s1, s2])
        result = await skill._execute_with_fallback(
            [s1, s2],
            AnalysisInput(data=[], question="q", step_id=1, execution_context=MagicMock()),
        )
        assert result.answer == "fallback ok"

    @pytest.mark.asyncio
    async def test_all_fail_returns_default(self):
        s1 = FakeStrategy("s1", None, execute_result=AnalysisResult(answer="", error="fail"))
        skill = make_skill(strategies=[s1])
        result = await skill._execute_with_fallback(
            [s1],
            AnalysisInput(data=[], question="q", step_id=1, execution_context=MagicMock()),
        )
        assert result.answer == "Не удалось проанализировать данные"


# ============================================================================
# _get_step_data
# ============================================================================

class FakeSession:
    """Фейковый SessionContext для тестов _get_step_data."""

    def __init__(self, steps=None, items=None):
        self.step_context = MagicMock()
        self.step_context.steps = steps or []
        self.data_context = MagicMock()
        self.data_context.get_item = MagicMock(return_value=items)


class FakeContextWithSession:
    """execution_context с session_context."""

    def __init__(self, session=None):
        self.session_context = session or FakeSession()


class FakeContextDirect:
    """execution_context БЕЗ session_context, но с step_context/data_context."""

    def __init__(self, session=None):
        if session:
            self.step_context = session.step_context
            self.data_context = session.data_context


class TestGetStepData:

    def _make_step(self, step_number, obs_ids=None):
        step = MagicMock()
        step.step_number = step_number
        step.observation_item_ids = obs_ids or []
        return step

    def test_found_step_with_rows_content(self):
        """Шаг найден, данные в формате {'rows': [...]}."""
        step = self._make_step(1, ["obs_1"])
        obs_item = MagicMock(content={"rows": [{"id": 1, "val": 10}]})
        session = FakeSession(steps=[step], items=obs_item)
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 1)
        assert result == [{"id": 1, "val": 10}]
        session.data_context.get_item.assert_called_once_with("obs_1", raise_on_missing=False)

    def test_found_step_with_data_key(self):
        """Шаг найден, данные в формате {'data': [...]}."""
        step = self._make_step(2, ["obs_2"])
        obs_item = MagicMock(content={"data": [{"x": 1}]})
        session = FakeSession(steps=[step], items=obs_item)
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 2)
        assert result == [{"x": 1}]

    def test_found_step_raw_content(self):
        """Шаг найден, данные без обёртки rows/data — возвращается as-is."""
        step = self._make_step(3, ["obs_3"])
        obs_item = MagicMock(content="plain text")
        session = FakeSession(steps=[step], items=obs_item)
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 3)
        assert result == "plain text"

    def test_step_not_found(self):
        """Шаг с указанным номером отсутствует."""
        step = self._make_step(1, ["obs_1"])
        session = FakeSession(steps=[step])
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 999)
        assert result is None

    def test_no_observation_ids(self):
        """Шаг есть, но observation_item_ids пуст."""
        step = self._make_step(1, [])
        session = FakeSession(steps=[step])
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 1)
        assert result is None

    def test_observation_item_not_found(self):
        """obs_id есть, но объект не найден в data_context."""
        step = self._make_step(1, ["obs_missing"])
        session = FakeSession(steps=[step])
        session.data_context.get_item.return_value = None
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 1)
        assert result is None

    def test_no_session_context(self):
        """execution_context не содержит session_context и не является сессией."""
        skill = make_skill()
        result = skill._get_step_data(MagicMock(spec=[]), 1)
        assert result is None

    def test_session_without_step_context(self):
        """session есть, но без step_context."""
        ctx = MagicMock()
        ctx.session_context = MagicMock(spec=[])  # нет step_context
        skill = make_skill()
        result = skill._get_step_data(ctx, 1)
        assert result is None

    def test_session_via_step_context_direct(self):
        """execution_context сам является сессией (имеет step_context)."""
        step = self._make_step(5, ["obs_5"])
        obs_item = MagicMock(content=[{"id": 1}])
        session = FakeSession(steps=[step], items=obs_item)
        skill = make_skill()
        result = skill._get_step_data(FakeContextDirect(session), 5)
        assert result == [{"id": 1}]

    def test_steps_not_a_list(self):
        """step_context.steps — не список."""
        session = FakeSession()
        session.step_context.steps = "not_a_list"
        skill = make_skill()
        result = skill._get_step_data(FakeContextWithSession(session), 1)
        assert result is None


# ============================================================================
# _get_session_context
# ============================================================================

class TestGetSessionContext:

    def test_with_session_context_attr(self):
        """context.session_context существует и имеет record_observation."""
        sc = MagicMock()
        sc.record_observation = MagicMock()
        ctx = MagicMock(session_context=sc)
        skill = make_skill()
        result = skill._get_session_context(ctx)
        assert result is sc

    def test_with_session_context_but_no_record_obs(self):
        """context.session_context есть, но без record_observation."""
        sc = MagicMock(spec=[])  # нет record_observation
        ctx = MagicMock(spec=[])  # никаких авто-атрибутов
        ctx.session_context = sc
        skill = make_skill()
        result = skill._get_session_context(ctx)
        assert result is None

    def test_with_private_session_context(self):
        """context._session_context существует и имеет record_observation (без session_context)."""
        sc = MagicMock()
        sc.record_observation = MagicMock()
        ctx = MagicMock(spec=[])
        ctx._session_context = sc
        skill = make_skill()
        result = skill._get_session_context(ctx)
        assert result is sc

    def test_no_session_at_all(self):
        """context не имеет ни session_context, ни _session_context."""
        skill = make_skill()
        result = skill._get_session_context(MagicMock(spec=[]))
        assert result is None


# ============================================================================
# _save_result_to_context
# ============================================================================

class TestSaveResultToContext:

    @pytest.mark.asyncio
    async def test_saves_observation(self):
        """Проверка, что record_observation вызывается с корректными параметрами."""
        sc = MagicMock()
        sc.record_observation = MagicMock(return_value="obs_id_1")
        ctx = MagicMock(session_context=sc)
        skill = make_skill()
        await skill._save_result_to_context(
            ctx, "тест", "ответ", 1, {"mode_used": "python"},
        )
        sc.record_observation.assert_called_once()
        call_kwargs = sc.record_observation.call_args[1]
        assert call_kwargs["source"] == "data_analysis.analyze_step_data"
        assert call_kwargs["step_number"] == 2  # step_id + 1
        assert "ответ" in call_kwargs["observation_data"]
        assert call_kwargs["metadata"]["skill"] == "data_analysis"
        assert call_kwargs["metadata"]["question"] == "тест"
        assert call_kwargs["metadata"]["mode_used"] == "python"

    @pytest.mark.asyncio
    async def test_no_session_does_not_raise(self):
        """Нет session_context — метод не должен бросать исключение."""
        skill = make_skill()
        await skill._save_result_to_context(
            MagicMock(spec=[]), "q", "answer", 1, {},
        )  # не должно упасть

    @pytest.mark.asyncio
    async def test_record_observation_error_does_not_raise(self):
        """Ошибка в record_observation не должна пробрасываться."""
        sc = MagicMock()
        sc.record_observation = MagicMock(side_effect=RuntimeError("DB error"))
        ctx = MagicMock(session_context=sc)
        skill = make_skill()
        await skill._save_result_to_context(ctx, "q", "a", 1, {})
        # метод должен перехватить исключение и не пробросить
