"""Контрактные тесты для observation-сигнала."""

from core.agent.components.observation_signal import ObservationSignalService
from core.models.data.execution import ExecutionResult


def test_observation_signal_contract_fields_for_success() -> None:
    """Сигнал успеха должен содержать фиксированный контракт полей."""
    service = ObservationSignalService()

    signal = service.build_signal(
        result=ExecutionResult.success(data={"value": 1}),
        action_name="planning.create_plan",
        parameters={},
    )

    assert signal["status"] == "success"
    assert signal["quality"] == "high"
    assert isinstance(signal["issues"], list)
    assert isinstance(signal["hint"], str)
    assert signal["next_step_hint"] == signal["hint"]


def test_observation_signal_contract_fields_for_error() -> None:
    """Сигнал ошибки должен соответствовать тому же контракту."""
    service = ObservationSignalService()

    signal = service.build_signal(
        result=ExecutionResult.failure("boom"),
        action_name="sql_tool.execute_query",
        parameters={"query": "SELECT 1"},
    )

    assert signal["status"] == "error"
    assert signal["quality"] == "low"
    assert "unknown_error" not in signal["issues"]
    assert isinstance(signal["hint"], str)
    assert signal["next_step_hint"] == signal["hint"]
