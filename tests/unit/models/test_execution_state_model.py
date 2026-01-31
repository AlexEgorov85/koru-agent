"""
Тесты для модели ExecutionState (ExecutionState, ExecutionStatus).
"""
import pytest
from models.execution_state import ExecutionState, ExecutionStatus


class TestExecutionStateModel:
    """Тесты для модели ExecutionState."""
    
    def test_execution_state_creation(self):
        """Тест создания ExecutionState."""
        state = ExecutionState(
            step=1,
            error_count=0,
            no_progress_steps=0,
            finished=False,
            metrics={"accuracy": 0.95, "speed": 1.2}
        )
        
        assert state.step == 1
        assert state.error_count == 0
        assert state.no_progress_steps == 0
        assert state.finished is False
        assert state.metrics == {"accuracy": 0.95, "speed": 1.2}
    
    def test_execution_state_with_optional_fields(self):
        """Тест создания ExecutionState с опциональными полями."""
        state = ExecutionState(
            step=5,
            error_count=2,
            no_progress_steps=1,
            finished=False,
            metrics={"precision": 0.8, "recall": 0.75},
            history=["action1", "action2", "action3"],
            current_plan_step="step_5"
        )
        
        assert state.history == ["action1", "action2", "action3"]
        assert state.current_plan_step == "step_5"
    
    def test_execution_state_default_values(self):
        """Тест значений по умолчанию для ExecutionState."""
        state = ExecutionState()
        
        assert state.step == 0  # значение по умолчанию
        assert state.error_count == 0   # значение по умолчанию
        assert state.no_progress_steps == 0  # значение по умолчанию
        assert state.finished is False  # значение по умолчанию
        assert state.metrics == {}      # значение по умолчанию
        assert state.history == []      # значение по умолчанию
        assert state.current_plan_step is None  # значение по умолчанию
    
    def test_execution_state_equality(self):
        """Тест равенства ExecutionState."""
        state1 = ExecutionState(
            step=1,
            error_count=0,
            no_progress_steps=0,
            finished=False,
            metrics={"test": "value"}
        )
        
        state2 = ExecutionState(
            step=1,
            error_count=0,
            no_progress_steps=0,
            finished=False,
            metrics={"test": "value"}
        )
        
        state3 = ExecutionState(
            step=2,  # другое значение
            error_count=0,
            no_progress_steps=0,
            finished=False,
            metrics={"test": "value"}
        )
        
        assert state1 == state2  # одинаковые по значению
        assert state1 != state3  # разные step
        assert state2 != state3  # разные step
    
    def test_execution_state_serialization(self):
        """Тест сериализации ExecutionState."""
        state = ExecutionState(
            step=3,
            error_count=1,
            no_progress_steps=2,
            finished=False,
            metrics={"loss": 0.1, "accuracy": 0.99},
            history=["init", "step1", "step2"],
            current_plan_step="step_3"
        )
        
        data = state.model_dump()
        
        assert data["step"] == 3
        assert data["error_count"] == 1
        assert data["no_progress_steps"] == 2
        assert data["finished"] is False
        assert data["metrics"] == {"loss": 0.1, "accuracy": 0.99}
        assert data["history"] == ["init", "step1", "step2"]
        assert data["current_plan_step"] == "step_3"
    
    def test_execution_state_from_dict(self):
        """Тест создания ExecutionState из словаря."""
        data = {
            "step": 7,
            "error_count": 3,
            "no_progress_steps": 0,
            "finished": True,
            "metrics": {"f1_score": 0.85, "auc": 0.92},
            "history": ["start", "analyze", "execute"],
            "current_plan_step": "step_7"
        }
        
        state = ExecutionState.model_validate(data)
        
        assert state.step == 7
        assert state.error_count == 3
        assert state.finished is True
        assert state.metrics == {"f1_score": 0.85, "auc": 0.92}
        assert state.history == ["start", "analyze", "execute"]
        assert state.current_plan_step == "step_7"
    
    def test_execution_state_register_error(self):
        """Тест метода register_error."""
        state = ExecutionState(step=1, error_count=0)
        
        state.register_error()
        
        assert state.error_count == 1
    
    def test_execution_state_register_progress(self):
        """Тест метода register_progress."""
        state = ExecutionState(step=1, no_progress_steps=2)
        
        # Регистрируем прогресс (progressed=True)
        state.register_progress(True)
        
        assert state.no_progress_steps == 0  # счетчик должен сброситься
        
        # Регистрируем отсутствие прогресса (progressed=False)
        state.register_progress(False)
        
        assert state.no_progress_steps == 1  # счетчик должен увеличиться
    
    def test_execution_state_complete(self):
        """Тест метода complete."""
        state = ExecutionState(step=1)
        
        state.complete()
        
        assert state.finished is True


def test_execution_status_enum_values():
    """Тест значений ExecutionStatus enum."""
    assert ExecutionStatus.INITIALIZING.value == "initializing"
    assert ExecutionStatus.IDLE.value == "idle"
    assert ExecutionStatus.ACTIVE.value == "active"
    assert ExecutionStatus.WAITING.value == "waiting"
    assert ExecutionStatus.COMPLETED.value == "completed"
    assert ExecutionStatus.ERROR.value == "error"
    assert ExecutionStatus.STOPPED.value == "stopped"
    assert ExecutionStatus.TERMINATED.value == "terminated"
    
    # Проверяем все значения
    all_statuses = [status.value for status in ExecutionStatus]
    expected_statuses = [
        "initializing", "idle", "active", "waiting", 
        "completed", "error", "stopped", "terminated"
    ]
    assert set(all_statuses) == set(expected_statuses)