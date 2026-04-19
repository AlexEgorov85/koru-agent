"""Тесты SQLRecoveryAnalyzer после выноса из AgentRuntime."""

from core.agent.components.sql_recovery import SQLRecoveryAnalyzer


def test_sql_recovery_analyzer_string_filter_hint() -> None:
    """Для строкового фильтра подсказка должна содержать нормализацию и LIKE-поиск."""
    analyzer = SQLRecoveryAnalyzer()

    result = analyzer.analyze_empty_result(
        {"query": "SELECT * FROM clients WHERE city = 'Paris'"}
    )

    assert "sql_filter_mismatch" in result["issues"]
    assert "LOWER(TRIM" in result["next_step_hint"]
    assert "LIKE" in result["next_step_hint"]


def test_sql_recovery_analyzer_year_filter_marks_year_issue() -> None:
    """Годовой фильтр должен помечаться специальным issue."""
    analyzer = SQLRecoveryAnalyzer()

    result = analyzer.analyze_empty_result(
        {"query": "SELECT * FROM sales WHERE year = 2025"}
    )

    assert "sql_filter_mismatch" in result["issues"]
    assert "sql_year_filter_mismatch" in result["issues"]
