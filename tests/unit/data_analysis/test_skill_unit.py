"""
Unit-тесты для оркестрации DataAnalysisSkill:
- _select_strategies (auto mode, mode override)
- _normalize_parameters
- _normalize_to_rows
- _execute_with_fallback
"""
from unittest.mock import AsyncMock, MagicMock
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
