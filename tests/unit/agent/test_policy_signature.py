"""Тесты policy с учётом action signature."""

from core.agent.components.policy import AgentPolicy, PolicyViolationError
from core.agent.state import AgentState
from core.agent.components.agent_metrics import AgentMetrics


def test_policy_allows_same_action_with_different_parameters() -> None:
    """Одинаковый action с разными параметрами не должен считаться повтором."""
    state = AgentState()
    policy = AgentPolicy()
    metrics = AgentMetrics()

    state.add_step(
        action_name="sql_tool.execute_query",
        status="COMPLETED",
        parameters={"query": "SELECT * FROM sales WHERE year = 2024"},
    )

    # Policy.evaluate теперь выбрасывает исключение при нарушении, иначе возвращает вердикт
    verdict = policy.evaluate(
        action_name="sql_tool.execute_query",
        metrics=metrics,
        parameters={"query": "SELECT * FROM sales WHERE year = 2025"}
    )

    assert verdict.allowed is True
    assert len(verdict.violations) == 0


def test_policy_blocks_same_action_with_same_parameters() -> None:
    """Одинаковый action и параметры должны блокироваться как repeat_action."""
    state = AgentState()
    policy = AgentPolicy()
    metrics = AgentMetrics()

    params = {"query": "SELECT * FROM sales WHERE year = 2025"}
    state.add_step(
        action_name="sql_tool.execute_query",
        status="COMPLETED",
        parameters=params,
    )

    # Симулируем повторное действие через metrics
    metrics.check_repeated_action = lambda name, params: name == "sql_tool.execute_query" and params == params
    metrics.repeated_actions_count = 3

    # При нарушении политики должно выбрасываться исключение
    try:
        policy.evaluate(
            action_name="sql_tool.execute_query",
            metrics=metrics,
            parameters=params
        )
        assert False, "Expected PolicyViolationError"
    except PolicyViolationError as e:
        assert "repeat_action" in str(e.verdict.violations[0])
