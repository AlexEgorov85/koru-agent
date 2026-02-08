"""
Сервис управления состоянием агента.
"""
from typing import Dict, Any, List, Optional
from domain.models.agent.agent_state import AgentState


class AgentStateManager:
    """
    Сервис управления состоянием агента.
    Содержит логику изменения состояния агента.
    """

    @staticmethod
    def register_error(state: AgentState) -> AgentState:
        """Регистрирует ошибку в состоянии агента."""
        return state.model_copy(
            update={
                "error_count": state.error_count + 1
            }
        )

    @staticmethod
    def register_progress(state: AgentState, progressed: bool) -> AgentState:
        """Регистрирует прогресс в состоянии агента."""
        no_progress_steps = state.no_progress_steps + 1 if not progressed else 0
        return state.model_copy(
            update={
                "no_progress_steps": no_progress_steps
            }
        )

    @staticmethod
    def complete(state: AgentState) -> AgentState:
        """Отмечает агента как завершившего выполнение."""
        return state.model_copy(
            update={
                "finished": True
            }
        )

    @staticmethod
    def increment_step(state: AgentState) -> AgentState:
        """Увеличивает счетчик шагов."""
        return state.model_copy(
            update={
                "step": state.step + 1
            }
        )

    @staticmethod
    def update_history(state: AgentState, new_entry: str) -> AgentState:
        """Обновляет историю агента."""
        new_history = state.history + [new_entry]
        return state.model_copy(
            update={
                "history": new_history
            }
        )

    @staticmethod
    def should_stop(state: AgentState, max_steps: int = 10, max_no_progress: int = 3) -> bool:
        """Проверяет, следует ли остановить выполнение."""
        return (
            state.step >= max_steps or
            state.no_progress_steps >= max_no_progress or
            state.finished
        )