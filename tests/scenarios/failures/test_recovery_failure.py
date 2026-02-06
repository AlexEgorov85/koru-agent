"""
Тест отказа восстановления - проверяет, что происходит, когда механизм восстановления сам по себе терпит неудачу
"""
import pytest
from tests.support.test_agent import TestAgent


@pytest.mark.failure
@pytest.mark.asyncio
async def test_recovery_failure():
    """Тест: когда восстановление также терпит неудачу"""
    # Для тестирования сбоя восстановления используем реального агента
    agent = TestAgent(recovery_policy=True, config={'max_steps': 2})
    result = await agent.run("Задача, которая может привести к сбою восстановления")
    
    # Проверяем, что тест завершается (не зацикливается)
    assert result.status in ["SUCCESS", "FAILED", "RECOVERED"]  # Может быть любым статусом, но не зависшим
    assert len(result.patterns_used) == 1
