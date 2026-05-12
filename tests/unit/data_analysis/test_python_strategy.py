"""
Unit-тесты для PythonStrategy.
"""
from unittest.mock import MagicMock
import pytest

from core.components.skills.data_analysis.strategies.python_strategy import PythonStrategy
from core.components.skills.data_analysis.base_strategy import AnalysisInput, AnalysisResult


def make_skill():
    return MagicMock(_context_window=8192, _max_new_tokens=2000)


def make_input(data, question="сумма", step_id=1, ctx=None):
    return AnalysisInput(
        data=data,
        question=question,
        step_id=step_id,
        execution_context=ctx or MagicMock(),
    )


# ============================================================================
# can_handle
# ============================================================================

class TestPythonStrategyCanHandle:

    def test_numeric_data_and_calc_keyword(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        assert strategy.can_handle(data, "сумма по a")

    def test_english_keyword(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        data = [{"value": 10}]
        assert strategy.can_handle(data, "sum of value")

    def test_non_numeric_data_returns_false(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        data = [{"name": "foo", "desc": "bar"}]
        assert not strategy.can_handle(data, "сумма")

    def test_numeric_data_without_calc_keyword_returns_false(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        data = [{"a": 1}]
        assert not strategy.can_handle(data, "какие тренды?")

    def test_empty_data_returns_false(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        assert not strategy.can_handle([], "сумма")

    def test_not_a_list_returns_false(self):
        skill = make_skill()
        strategy = PythonStrategy(skill)
        assert not strategy.can_handle("not a list", "сумма")


# ============================================================================
# execute
# ============================================================================

class TestPythonStrategyExecute:

    @pytest.mark.asyncio
    async def test_count(self):
        strategy = PythonStrategy(make_skill())
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = await strategy.execute(make_input(data, "сколько записей?"))
        assert isinstance(result, AnalysisResult)
        assert result.confidence == 0.95
        assert "count" in result.operations
        assert "3" in result.answer

    @pytest.mark.asyncio
    async def test_sum(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": 20}, {"val": 30}]
        result = await strategy.execute(make_input(data, "сумма val"))
        assert "sum_val" in result.answer
        assert "60" in result.answer
        assert "sum:val" in result.operations

    @pytest.mark.asyncio
    async def test_average(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": 20}, {"val": 30}]
        result = await strategy.execute(make_input(data, "среднее val"))
        assert "avg_val" in result.answer
        assert "avg_val: 20" in result.answer
        assert "avg:val" in result.operations

    @pytest.mark.asyncio
    async def test_min_max(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": 5}, {"val": 30}]
        result = await strategy.execute(make_input(data, "мин и макс val"))
        assert "min_val" in result.answer
        assert "max_val" in result.answer
        assert "5" in result.answer  # min=5
        assert "30" in result.answer  # max=30

    @pytest.mark.asyncio
    async def test_multiple_operations(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": 20}]
        result = await strategy.execute(make_input(data, "сумма и среднее val"))
        assert "sum_val" in result.answer
        assert "avg_val" in result.answer
        assert "sum:val" in result.operations
        assert "avg:val" in result.operations

    @pytest.mark.asyncio
    async def test_no_known_keyword_returns_info(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}]
        result = await strategy.execute(make_input(data, "непонятный запрос"))
        assert result.operations == ["info"]
        assert result.confidence == 0.3
        assert "count" in result.answer or "info" in result.metadata.get("mode_used", "")

    @pytest.mark.asyncio
    async def test_none_values_skip_min_max(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": None}, {"val": 30}]
        result = await strategy.execute(make_input(data, "мин и макс val"))
        assert "min_val" in result.answer
        assert "max_val" in result.answer
        assert "10" in result.answer
        assert "30" in result.answer

    @pytest.mark.asyncio
    async def test_none_values_treated_as_zero_in_sum_avg(self):
        strategy = PythonStrategy(make_skill())
        data = [{"val": 10}, {"val": None}, {"val": 30}]
        result = await strategy.execute(make_input(data, "сумма и среднее val"))
        assert "sum_val" in result.answer
        assert "avg_val" in result.answer
        assert "40" in result.answer          # 10 + 0 + 30
        assert "avg_val: 13." in result.answer  # 40/3 ≈ 13.33

    @pytest.mark.asyncio
    async def test_multiple_numeric_fields(self):
        strategy = PythonStrategy(make_skill())
        data = [{"a": 10, "b": 100}, {"a": 20, "b": 200}]
        result = await strategy.execute(make_input(data, "сумма a и b"))
        assert "sum_a: 30" in result.answer   # 10 + 20
        assert "sum_b: 300" in result.answer  # 100 + 200
        assert "sum:a" in result.operations
        assert "sum:b" in result.operations
