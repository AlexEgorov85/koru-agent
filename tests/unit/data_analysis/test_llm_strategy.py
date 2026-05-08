"""
Unit-тесты для LLMStrategy.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.components.skills.data_analysis.strategies.llm_strategy import LLMStrategy
from core.components.skills.data_analysis.base_strategy import AnalysisInput, AnalysisResult


class FakeContext:
    """Пустой контекст — _get_executor падает на skill.executor."""


def make_mock_skill(
    prompt_content="Ты аналитик",
    user_prompt_content="Вопрос: {question}\nДанные: {content}",
    output_contract=None,
    executor_result_data=None,
    executor_side_effect=None,
    context_window=8192,
    max_new_tokens=2000,
):
    """Создаёт mock скилла с подменой промптов и executor."""
    skill = MagicMock()
    skill._context_window = context_window
    skill._max_new_tokens = max_new_tokens

    # prompts
    skill.get_prompt = MagicMock()
    system = MagicMock()
    system.content = prompt_content
    skill.get_prompt.side_effect = lambda name: {
        "data_analysis.analyze_step_data.system": system if prompt_content is not None else None,
        "data_analysis.analyze_step_data.user": MagicMock(content=user_prompt_content) if user_prompt_content is not None else None,
    }.get(name)

    # executor
    executor = MagicMock()
    executor.execute_action = AsyncMock()
    if executor_side_effect:
        executor.execute_action.side_effect = executor_side_effect
    else:
        from core.models.data.execution import ExecutionStatus
        exec_result = MagicMock()
        exec_result.status = ExecutionStatus.COMPLETED
        exec_result.data = executor_result_data or {"answer": "Тестовый ответ", "confidence": 0.8}
        executor.execute_action.return_value = exec_result

    skill.executor = executor
    skill.get_output_contract = MagicMock(return_value=output_contract or MagicMock())
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

class TestLLMStrategyCanHandle:

    def test_small_data_fits_context(self):
        skill = make_mock_skill()
        strategy = LLMStrategy(skill)
        data = [{"a": 1, "b": "hello"}]
        assert strategy.can_handle(data, "короткий вопрос")

    def test_large_data_exceeds_context(self):
        skill = make_mock_skill(context_window=1000, max_new_tokens=200)
        strategy = LLMStrategy(skill)
        data = [{"x": "a" * 500}] * 20
        assert not strategy.can_handle(data, "вопрос " * 50)

    def test_empty_data_returns_false(self):
        skill = make_mock_skill()
        strategy = LLMStrategy(skill)
        assert not strategy.can_handle([], "вопрос")


# ============================================================================
# execute
# ============================================================================

class TestLLMStrategyExecute:

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        skill = make_mock_skill(
            executor_result_data={"answer": "Успешный ответ", "confidence": 0.9},
        )
        strategy = LLMStrategy(skill)
        data = [{"id": 1, "val": 100}]
        result = await strategy.execute(make_input(data, "какие данные?"))
        assert isinstance(result, AnalysisResult)
        assert result.answer == "Успешный ответ"
        assert result.confidence == 0.9
        assert "llm" in result.operations

    @pytest.mark.asyncio
    async def test_missing_system_prompt(self):
        skill = make_mock_skill(prompt_content=None)
        strategy = LLMStrategy(skill)
        data = [{"id": 1}]
        result = await strategy.execute(make_input(data, "вопрос"))
        assert result.answer == ""
        assert result.confidence == 0.0
        assert result.error == "Промпты не загружены"

    @pytest.mark.asyncio
    async def test_executor_returns_error(self):
        skill = make_mock_skill(executor_side_effect=Exception("LLM timeout"))
        strategy = LLMStrategy(skill)
        data = [{"id": 1}]
        result = await strategy.execute(make_input(data, "вопрос"))
        assert result.answer == ""
        assert "LLM timeout" in (result.error or "")

    @pytest.mark.asyncio
    async def test_executor_returns_failed_status(self):
        from core.models.data.execution import ExecutionStatus
        skill = make_mock_skill()
        exec_result = MagicMock()
        exec_result.status = ExecutionStatus.FAILED
        exec_result.data = None
        exec_result.error = "Generation failed"
        skill.executor.execute_action.return_value = exec_result
        strategy = LLMStrategy(skill)
        result = await strategy.execute(make_input([{"id": 1}], "вопрос"))
        assert result.answer == ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_handles_pydantic_response(self):
        """LLMStrategy должна обрабатывать Pydantic model в result.data."""
        class FakeModel:
            def model_dump(self):
                return {"answer": "Из модели", "confidence": 0.75}

        skill = make_mock_skill(executor_result_data=FakeModel())
        strategy = LLMStrategy(skill)
        result = await strategy.execute(make_input([{"id": 1}], "вопрос"))
        assert result.answer == "Из модели"
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_uses_correct_structured_output_params(self):
        skill = make_mock_skill(
            executor_result_data={"answer": "OK", "confidence": 0.8},
            output_contract="fake_contract",
        )
        strategy = LLMStrategy(skill)
        await strategy.execute(make_input([{"id": 1}], "вопрос"))

        call_args = skill.executor.execute_action.call_args
        params = call_args[1]["parameters"]
        structured = params["structured_output"]
        assert structured["output_model"] == "data_analysis.analyze_step_data.output"
        assert structured["schema_def"] == "fake_contract"
        assert structured["strict_mode"] is True
        assert structured["max_retries"] == 0
        assert params["temperature"] == 0.2
