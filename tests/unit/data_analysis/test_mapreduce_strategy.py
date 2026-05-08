"""
Unit-тесты для MapReduceStrategy (изолированно, без LLM).
"""
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.components.skills.data_analysis.strategies.mapreduce_strategy import MapReduceStrategy
from core.components.skills.data_analysis.base_strategy import AnalysisInput, AnalysisResult


class FakeContext:
    """Пустой контекст — _get_executor падает на skill.executor."""


def make_mock_skill(
    system_prompt="Ты аналитик. Верни связный текст.",
    user_prompt="Вопрос: {question}\nФрагменты:\n{fragments}",
    merge_system="Объедини фрагменты.",
    merge_user="Вопрос: {question}\n{fragments}",
    context_window=8192,
    max_new_tokens=2000,
    map_result_content="В этом чанке содержатся данные о продажах. Общая сумма: 150000 рублей.",
):
    skill = MagicMock()
    skill._context_window = context_window
    skill._max_new_tokens = max_new_tokens

    def get_prompt(name):
        contents = {
            "data_analysis.analyze_step_data.system": system_prompt,
            "data_analysis.analyze_step_data.user": user_prompt,
            "data_analysis.merge_step_data.system": merge_system,
            "data_analysis.merge_step_data.user": merge_user,
        }
        c = contents.get(name)
        if c is None:
            return None
        m = MagicMock()
        m.content = c
        return m

    skill.get_prompt = MagicMock(side_effect=get_prompt)

    executor = MagicMock()
    executor.execute_action = AsyncMock()
    from core.models.data.execution import ExecutionStatus
    exec_result = MagicMock()
    exec_result.status = ExecutionStatus.COMPLETED
    exec_result.data = {"content": map_result_content}
    executor.execute_action.return_value = exec_result

    skill.executor = executor
    return skill


def make_input(data, question="тест", step_id=1, ctx=None):
    return AnalysisInput(
        data=data,
        question=question,
        step_id=step_id,
        execution_context=ctx or FakeContext(),
    )


# ============================================================================
# can_handle
# ============================================================================

class TestMapReduceStrategyCanHandle:

    def test_non_empty_data_returns_true(self):
        strategy = MapReduceStrategy(make_mock_skill())
        assert strategy.can_handle([{"a": 1}], "вопрос")

    def test_empty_data_returns_false(self):
        strategy = MapReduceStrategy(make_mock_skill())
        assert not strategy.can_handle([], "вопрос")

    def test_none_data_returns_false(self):
        strategy = MapReduceStrategy(make_mock_skill())
        assert not strategy.can_handle(None, "вопрос")


# ============================================================================
# _calculate_max_chars
# ============================================================================

class TestCalculateMaxChars:

    def test_basic_calculation(self):
        strategy = MapReduceStrategy(make_mock_skill())
        result = strategy._calculate_max_chars(
            prompt_chars=200, context_window=8192, max_new_tokens=2000,
        )
        assert isinstance(result, int)
        assert 1000 < result < 20000

    def test_uses_safety_factor(self):
        strategy = MapReduceStrategy(make_mock_skill())
        result = strategy._calculate_max_chars(
            prompt_chars=200, context_window=8192, max_new_tokens=2000,
            safety_factor=0.5,
        )
        assert result > 0

    def test_minimum_floor(self):
        strategy = MapReduceStrategy(make_mock_skill())
        # super small context: min content tokens = 1000, chars = 3000, * safety = 2550
        result = strategy._calculate_max_chars(
            prompt_chars=5000, context_window=1000, max_new_tokens=500,
        )
        assert result == 2550


# ============================================================================
# _create_context_batches
# ============================================================================

class TestCreateContextBatches:

    def test_single_item_returns_one_batch(self):
        strategy = MapReduceStrategy(make_mock_skill())
        items = [{"content": "a" * 100}]
        batches = strategy._create_context_batches(items, "вопрос?", 8192, 2000)
        assert len(batches) == 1

    def test_large_items_split_into_multiple_batches(self):
        strategy = MapReduceStrategy(make_mock_skill())
        items = [{"content": "x" * 5000} for _ in range(10)]
        batches = strategy._create_context_batches(items, "вопрос?", 2000, 200)
        assert len(batches) >= 2

    def test_empty_items_returns_empty(self):
        strategy = MapReduceStrategy(make_mock_skill())
        batches = strategy._create_context_batches([], "вопрос?", 8192, 2000)
        assert batches == []

    def test_context_respects_individual_items(self):
        strategy = MapReduceStrategy(make_mock_skill())
        item = {"content": "a" * 100000}
        # giant item should still be in its own batch
        batches = strategy._create_context_batches([item], "q?", 2000, 200)
        assert len(batches) >= 1


# ============================================================================
# _extract_schema
# ============================================================================

class TestExtractSchema:

    def test_extracts_keys_from_first_row(self):
        strategy = MapReduceStrategy(make_mock_skill())
        data = [{"id": 1, "name": "foo", "value": 10}]
        schema = strategy._extract_schema(data)
        assert "id" in schema
        assert "name" in schema
        assert "value" in schema

    def test_empty_data_returns_empty(self):
        strategy = MapReduceStrategy(make_mock_skill())
        assert strategy._extract_schema([]) == ""

    def test_non_dict_data_returns_empty(self):
        strategy = MapReduceStrategy(make_mock_skill())
        assert strategy._extract_schema([1, 2, 3]) == ""


# ============================================================================
# _inject_schema
# ============================================================================

class TestInjectSchema:

    def test_injects_schema_into_chunks(self):
        strategy = MapReduceStrategy(make_mock_skill())
        chunks = [{"content": "факт 1", "chunk_id": 0}]
        result = strategy._inject_schema(chunks, "СТРУКТУРА ДАННЫХ: id, name")
        assert result[0]["content"].startswith("СТРУКТУРА ДАННЫХ")

    def test_skips_if_already_has_schema(self):
        strategy = MapReduceStrategy(make_mock_skill())
        chunks = [{"content": "СТРУКТУРА ДАННЫХ: id", "chunk_id": 0}]
        result = strategy._inject_schema(chunks, "СТРУКТУРА ДАННЫХ: x")
        assert result[0]["content"] == "СТРУКТУРА ДАННЫХ: id"

    def test_no_schema_no_change(self):
        strategy = MapReduceStrategy(make_mock_skill())
        chunks = [{"content": "факт", "chunk_id": 0}]
        result = strategy._inject_schema(chunks, "")
        assert result[0]["content"] == "факт"


# ============================================================================
# _filter_empty_summaries
# ============================================================================

class TestFilterEmptySummaries:

    def test_keeps_valid_content(self):
        strategy = MapReduceStrategy(make_mock_skill())
        summaries = [{"content": "В регионе МСК продажи выросли", "chunk_id": 0}]
        result = strategy._filter_empty_summaries(summaries)
        assert len(result) == 1

    def test_removes_empty_content(self):
        strategy = MapReduceStrategy(make_mock_skill())
        summaries = [{"content": "", "chunk_id": 0}]
        result = strategy._filter_empty_summaries(summaries)
        assert len(result) == 0

    def test_removes_noise(self):
        strategy = MapReduceStrategy(make_mock_skill())
        summaries = [
            {"content": "Нет данных для анализа", "chunk_id": 0},
            {"content": "не удалось извлечь информацию", "chunk_id": 1},
            {"content": "В регионе МСК продажи выросли на 15%", "chunk_id": 2},
        ]
        result = strategy._filter_empty_summaries(summaries)
        assert len(result) == 1
        assert result[0]["chunk_id"] == 2

    def test_removes_short_content(self):
        strategy = MapReduceStrategy(make_mock_skill())
        summaries = [{"content": "коротко", "chunk_id": 0}]
        result = strategy._filter_empty_summaries(summaries)
        assert len(result) == 0


# ============================================================================
# _map_phase (mocked LLM)
# ============================================================================

class TestMapPhase:

    @pytest.mark.asyncio
    async def test_single_chunk(self):
        strategy = MapReduceStrategy(make_mock_skill())
        result = await strategy._map_phase(
            [{"content": "данные", "chunk_id": 0}],
            "вопрос?", MagicMock(),
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_chunks(self):
        strategy = MapReduceStrategy(make_mock_skill())
        result = await strategy._map_phase([], "вопрос?", MagicMock())
        assert result == []


# ============================================================================
# _tree_reduce
# ============================================================================

class TestTreeReduce:

    @pytest.mark.asyncio
    async def test_single_summary(self):
        strategy = MapReduceStrategy(make_mock_skill())
        summaries = [{"content": "единственный результат", "chunk_id": 0}]
        result = await strategy._tree_reduce(summaries, "вопрос?", MagicMock(), 8192, 2000)
        assert result == "единственный результат"

    @pytest.mark.asyncio
    async def test_empty_summaries(self):
        strategy = MapReduceStrategy(make_mock_skill())
        result = await strategy._tree_reduce([], "вопрос?", MagicMock(), 8192, 2000)
        assert result == "Нет данных для анализа"


# ============================================================================
# execute (full flow, mocked LLM)
# ============================================================================

class TestMapReduceExecute:

    @pytest.mark.asyncio
    async def test_small_data_returns_result(self):
        skill = make_mock_skill()
        strategy = MapReduceStrategy(skill)
        data = [{"id": i, "val": i * 10} for i in range(5)]
        result = await strategy.execute(make_input(data, "анализ?"))
        assert isinstance(result, AnalysisResult)
        assert result.answer
        assert result.confidence == 0.85
        assert any("map" in op for op in result.operations)

    @pytest.mark.asyncio
    async def test_empty_data_no_answer(self):
        strategy = MapReduceStrategy(make_mock_skill())
        data = []
        result = await strategy.execute(make_input(data, "анализ?"))
        assert result.answer == "Не удалось извлечь релевантную информацию из данных"
        assert result.confidence == 0.3


# ============================================================================
# _chunk_data
# ============================================================================

class TestChunkData:

    def test_chunks_are_created(self):
        strategy = MapReduceStrategy(make_mock_skill())
        data = [{"id": i, "val": f"x" * 100} for i in range(20)]
        chunks = strategy._chunk_data(data, max_chunk_chars=500)
        assert len(chunks) > 1
        for c in chunks:
            assert "content" in c
            assert "chunk_id" in c
