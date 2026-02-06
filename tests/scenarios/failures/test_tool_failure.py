"""
Тест сбоя инструмента - проверяет, как агент обрабатывает ошибки инструментов
"""
import pytest
from tests.support.test_agent import TestAgent, ScriptedTool


@pytest.mark.failure
@pytest.mark.asyncio
async def test_tool_failure_triggers_recovery():
    """Тест: ошибка инструмента вызывает восстановление"""
    # Создаем инструмент, который возвращает ошибку
    failing_tool = ScriptedTool([Exception("Critical error")])
    agent = TestAgent(tools={"failing_tool": failing_tool}, recovery_policy=True, config={'max_steps': 2})
    result = await agent.run("Задача с критическим инструментом")
    
    # Проверяем, что тест завершается (не зацикливается)
    assert result.status in ["SUCCESS", "FAILED", "RECOVERED"]  # Может быть любым статусом, но не зависшим
    assert len(result.patterns_used) == 1
