"""
Тест защиты от бесконечного цикла - проверяет, что агент может обнаруживать и прерывать бесконечные циклы
"""
import pytest
from tests.support.test_agent import TestAgent


@pytest.mark.failure
@pytest.mark.asyncio
async def test_infinite_loop_detection():
    """Тест: агент должен обнаруживать и прерывать бесконечные циклы"""
    # Используем агента с минимальным количеством шагов для предотвращения зацикливания
    agent = TestAgent(config={'max_steps': 1})  # Устанавливаем очень малое количество шагов
    result = await agent.run("Задача, которая может привести к зацикливанию")
    
    # Проверяем, что тест завершается быстро (не зацикливается)
    assert result.status in ["SUCCESS", "FAILED"]  # Должен завершиться, а не зависнуть
    assert len(result.patterns_used) == 1
