"""Тесты policy с учётом action signature."""

from core.agent.components.policy import AgentPolicy
from core.agent.state import AgentState


def test_policy_allows_same_action_with_different_parameters() -> None:
    """Одинаковый action с разными параметрами не должен считаться повтором."""
    state = AgentState()
    policy = AgentPolicy()

    state.add_step(
        action_name="sql_tool.execute_query",
        status="COMPLETED",
        parameters={"query": "SELECT * FROM sales WHERE year = 2024"},
    )

    allowed, reason = policy.check_step(
        action_name="sql_tool.execute_query",
        parameters={"query": "SELECT * FROM sales WHERE year = 2025"},
        state=state,
    )

    assert allowed is True
    assert reason == ""


def test_policy_blocks_same_action_with_same_parameters() -> None:
    """Одинаковый action и параметры должны блокироваться как repeat_action."""
    state = AgentState()
    policy = AgentPolicy()

    params = {"query": "SELECT * FROM sales WHERE year = 2025"}
    state.add_step(
        action_name="sql_tool.execute_query",
        status="COMPLETED",
        parameters=params,
    )

    allowed, reason = policy.check_step(
        action_name="sql_tool.execute_query",
        parameters=params,
        state=state,
    )

    assert allowed is False
    assert reason == "repeat_action"
