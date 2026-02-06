"""
Тест обработки галлюцинаций LLM - проверяет, как агент справляется с некорректными или бредовыми ответами от LLM
"""
import pytest
from tests.support.test_agent import TestAgent, DeterministicLLM


@pytest.mark.failure
@pytest.mark.asyncio
async def test_llm_hallucination_handling():
    """Тест: как агент справляется с галлюцинациями LLM"""
    # Используем детерминированный LLM с контролируемым поведением
    deterministic_llm = DeterministicLLM(["Это бессвязный ответ", "Второй бессвязный ответ", "Корректный ответ"])
    agent = TestAgent(llm=deterministic_llm, config={'max_steps': 2})
    result = await agent.run("Обычная задача")
    
    # Проверяем, что тест завершается (не зацикливается)
    assert result.status in ["SUCCESS", "FAILED"]  # Должен завершиться, а не зависнуть
    assert len(result.patterns_used) == 1
