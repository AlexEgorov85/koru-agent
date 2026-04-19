"""Тесты observation-сигналов runtime для пустых SQL-ответов."""

from core.agent.runtime import AgentRuntime
from core.models.data.execution import ExecutionResult


def test_build_observation_signal_sql_year_empty_adds_year_hint() -> None:
    """Пустой SQL-ответ с фильтром по году должен давать подсказку проверить доступные годы."""
    runtime = AgentRuntime.__new__(AgentRuntime)

    result = ExecutionResult.success(data=[])
    signal = runtime._build_observation_signal(
        result=result,
        action_name="sql_tool.execute_query",
        parameters={"query": "SELECT * FROM sales WHERE year = 2025"},
    )

    assert signal["status"] == "empty"
    assert "sql_filter_mismatch" in signal["issues"]
    assert "sql_year_filter_mismatch" in signal["issues"]
    assert "GROUP BY" in signal["next_step_hint"] or "MIN(" in signal["next_step_hint"]
    assert "year" in signal["next_step_hint"].lower()


def test_build_observation_signal_sql_string_filter_adds_universal_hint() -> None:
    """Пустой SQL-ответ с НЕ-датовым фильтром тоже должен получать диагностику фильтров."""
    runtime = AgentRuntime.__new__(AgentRuntime)

    result = ExecutionResult.success(data=[])
    signal = runtime._build_observation_signal(
        result=result,
        action_name="sql_tool.execute_query",
        parameters={"query": "SELECT * FROM clients WHERE city = 'Paris'"},
    )

    assert signal["status"] == "empty"
    assert "sql_filter_mismatch" in signal["issues"]
    assert "sql_year_filter_mismatch" not in signal["issues"]
    assert "LOWER(TRIM" in signal["next_step_hint"]
    assert "LIKE" in signal["next_step_hint"]
    assert "city" in signal["next_step_hint"].lower()


def test_build_observation_signal_non_sql_empty_has_default_hint() -> None:
    """Для не-SQL действий остаётся базовая подсказка при пустом результате."""
    runtime = AgentRuntime.__new__(AgentRuntime)

    result = ExecutionResult.success(data=[])
    signal = runtime._build_observation_signal(
        result=result,
        action_name="planning.create_plan",
        parameters={},
    )

    assert signal["status"] == "empty"
    assert signal["issues"] == ["empty_result"]
    assert signal["next_step_hint"] == "Уточни параметры или выбери другой инструмент"
