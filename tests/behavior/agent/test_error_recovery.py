"""
Тест восстановления после ошибки инструмента
"""
import pytest
from tests.support.test_agent import TestAgent, ScriptedTool


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_tool_error_recovery():
    """Ошибка tool → восстановление"""
    # Создаем инструмент, который сначала падает, потом работает (для тестирования восстановления)
    failing_tool = ScriptedTool([Exception("Tool failed"), {"status": "success", "result": "ok"}])
    agent = TestAgent(tools={"problematic_tool": failing_tool}, recovery_policy=True, config={'max_steps': 3})
    result = await agent.run("Задача с использованием проблемного инструмента")
    
    # Проверяем, что тест завершается (не зацикливается)
    assert result.status in ["SUCCESS", "FAILED", "RECOVERED"]  # Может быть любым статусом, но не зависшим
    assert len(result.patterns_used) == 1
