"""
Сервис управления состоянием композиционного паттерна.
"""
from typing import Dict, Any, Optional, List
from domain.models.composable_pattern_state import ComposablePatternState, ComposablePatternStatus
from datetime import datetime


class ComposablePatternStateManager:
    """
    Сервис управления состоянием композиционного паттерна.
    Содержит логику изменения состояния композиционного паттерна.
    """

    @staticmethod
    def start_execution(state: ComposablePatternState, pattern_name: str, description: str = "") -> ComposablePatternState:
        """Начать выполнение паттерна"""
        return state.model_copy(
            update={
                "pattern_name": pattern_name,
                "status": ComposablePatternStatus.ACTIVE,
                "started_at": datetime.utcnow(),
                "metadata": {**state.metadata, "description": description},
                "step_count": 0,
                "iteration_count": 0,
                "error_count": 0,
                "no_progress_iterations": 0
            }
        )

    @staticmethod
    def start_iteration(state: ComposablePatternState) -> ComposablePatternState:
        """Начать новую итерацию ReAct"""
        return state.model_copy(
            update={
                "iteration_count": state.iteration_count + 1,
                "step_count": state.step_count + 1,
                "current_thought": None,
                "current_action": None,
                "current_observation": None
            }
        )

    @staticmethod
    def record_thought(state: ComposablePatternState, thought: str) -> ComposablePatternState:
        """Записать мышление в текущую итерацию"""
        new_thought_history = state.thought_history + [thought]
        return state.model_copy(
            update={
                "current_thought": thought,
                "thought_history": new_thought_history
            }
        )

    @staticmethod
    def record_action(state: ComposablePatternState, action: Dict[str, Any]) -> ComposablePatternState:
        """Записать действие в текущую итерацию"""
        new_action_entry = {
            "step": state.step_count,
            "action": action,
            "timestamp": datetime.utcnow(),
            "iteration": state.iteration_count
        }
        new_action_history = state.action_history + [new_action_entry]
        return state.model_copy(
            update={
                "current_action": action,
                "action_history": new_action_history
            }
        )

    @staticmethod
    def record_observation(state: ComposablePatternState, observation: str) -> ComposablePatternState:
        """Записать наблюдение в текущую итерацию"""
        new_observation_history = state.observation_history + [observation]
        return state.model_copy(
            update={
                "current_observation": observation,
                "observation_history": new_observation_history
            }
        )

    @staticmethod
    def register_error(state: ComposablePatternState) -> ComposablePatternState:
        """Зарегистрировать ошибку"""
        return state.model_copy(
            update={
                "error_count": state.error_count + 1
            }
        )

    @staticmethod
    def register_progress(state: ComposablePatternState, progressed: bool) -> ComposablePatternState:
        """Зарегистрировать прогресс"""
        no_progress_iterations = state.no_progress_iterations + 1 if not progressed else 0
        progress_percentage = state.progress_percentage
        last_progress_update = state.last_progress_update
        
        if progressed:
            no_progress_iterations = 0
            last_progress_update = datetime.utcnow()
            progress_percentage = min(100.0, state.progress_percentage + 5.0)

        return state.model_copy(
            update={
                "no_progress_iterations": no_progress_iterations,
                "progress_percentage": progress_percentage,
                "last_progress_update": last_progress_update
            }
        )

    @staticmethod
    def complete(state: ComposablePatternState) -> ComposablePatternState:
        """Отметить паттерн как завершенный"""
        return state.model_copy(
            update={
                "status": ComposablePatternStatus.COMPLETED,
                "finished": True,
                "finished_at": datetime.utcnow()
            }
        )

    @staticmethod
    def pause(state: ComposablePatternState) -> ComposablePatternState:
        """Приостановить выполнение паттерна"""
        return state.model_copy(
            update={
                "status": ComposablePatternStatus.PAUSED
            }
        )

    @staticmethod
    def resume(state: ComposablePatternState) -> ComposablePatternState:
        """Возобновить выполнение паттерна"""
        return state.model_copy(
            update={
                "status": ComposablePatternStatus.ACTIVE
            }
        )

    @staticmethod
    def waiting_for_input(state: ComposablePatternState) -> ComposablePatternState:
        """Отметить паттерн как ожидающий ввода"""
        return state.model_copy(
            update={
                "status": ComposablePatternStatus.WAITING_FOR_INPUT
            }
        )

    @staticmethod
    def fail(state: ComposablePatternState, error_details: Optional[Dict[str, Any]] = None) -> ComposablePatternState:
        """Отметить паттерн как завершенный с ошибкой"""
        updates = {
            "status": ComposablePatternStatus.FAILED,
            "finished": True,
            "finished_at": datetime.utcnow()
        }
        if error_details:
            updates["error_details"] = error_details

        return state.model_copy(update=updates)

    @staticmethod
    def add_to_undo_stack(state: ComposablePatternState, operation: Dict[str, Any]) -> ComposablePatternState:
        """Добавить операцию в стек отмены"""
        new_undo_stack = state.undo_stack + [operation]
        return state.model_copy(
            update={
                "undo_stack": new_undo_stack
            }
        )

    @staticmethod
    def pop_from_undo_stack(state: ComposablePatternState) -> tuple[ComposablePatternState, Optional[Dict[str, Any]]]:
        """Извлечь последнюю операцию из стека отмены"""
        if state.undo_stack:
            new_undo_stack = state.undo_stack[:-1]
            popped_operation = state.undo_stack[-1]
            new_state = state.model_copy(update={"undo_stack": new_undo_stack})
            return new_state, popped_operation
        return state, None

    @staticmethod
    def is_max_iterations_reached(state: ComposablePatternState) -> bool:
        """Проверить, достигнуто ли максимальное количество итераций"""
        return state.iteration_count >= state.max_iterations

    @staticmethod
    def is_no_progress_limit_reached(state: ComposablePatternState) -> bool:
        """Проверить, достигнуто ли ограничение на итерации без прогресса"""
        return state.no_progress_iterations >= state.max_no_progress_iterations

    @staticmethod
    def should_continue(state: ComposablePatternState) -> bool:
        """Проверить, следует ли продолжать выполнение"""
        return (
            not state.finished and
            not ComposablePatternStateManager.is_max_iterations_reached(state) and
            not ComposablePatternStateManager.is_no_progress_limit_reached(state)
        )