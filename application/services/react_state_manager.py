"""
Сервис управления состоянием ReAct.
"""
from typing import List, Dict, Any, Optional
from domain.models.react_state import ReActState, ReActStep, ActionType


class ReActStateManager:
    """
    Сервис управления состоянием ReAct.
    Содержит логику изменения состояния ReAct.
    """

    @staticmethod
    def add_step(state: ReActState, action_type: ActionType, content: str, metadata: Optional[Dict[str, Any]] = None) -> ReActState:
        """Добавить шаг в историю"""
        new_step = ReActStep(
            step_number=len(state.steps),
            action_type=action_type,
            content=content,
            metadata=metadata
        )
        
        # Создаем новое состояние с обновленными данными
        new_steps = state.steps + [new_step]
        new_metrics = state.metrics.copy() if state.metrics else {}
        new_metrics["total_steps"] = new_metrics.get("total_steps", 0) + 1
        
        if action_type in [ActionType.THOUGHT, ActionType.REASONING]:
            new_metrics["thought_count"] = new_metrics.get("thought_count", 0) + 1
        elif action_type == ActionType.ACTION:
            new_metrics["action_count"] = new_metrics.get("action_count", 0) + 1
        elif action_type == ActionType.OBSERVATION:
            new_metrics["observation_count"] = new_metrics.get("observation_count", 0) + 1

        return ReActState(
            goal=state.goal,
            steps=new_steps,
            current_step=state.current_step + 1,
            is_completed=state.is_completed,
            completion_reason=state.completion_reason,
            context=state.context,
            metrics=new_metrics
        )

    @staticmethod
    def get_recent_thoughts(state: ReActState, count: int = 1) -> List[ReActStep]:
        """Получить последние рассуждения"""
        thoughts = [step for step in state.steps
                   if step.action_type in [ActionType.THOUGHT, ActionType.REASONING]]
        return thoughts[-count:]

    @staticmethod
    def get_recent_actions(state: ReActState, count: int = 1) -> List[ReActStep]:
        """Получить последние действия"""
        actions = [step for step in state.steps if step.action_type == ActionType.ACTION]
        return actions[-count:]

    @staticmethod
    def get_recent_observations(state: ReActState, count: int = 1) -> List[ReActStep]:
        """Получить последние наблюдения"""
        observations = [step for step in state.steps if step.action_type == ActionType.OBSERVATION]
        return observations[-count:]

    @staticmethod
    def mark_completed(state: ReActState, reason: str = "Цель достигнута") -> ReActState:
        """Отметить выполнение задачи как завершенное"""
        return ReActState(
            goal=state.goal,
            steps=state.steps,
            current_step=state.current_step,
            is_completed=True,
            completion_reason=reason,
            context=state.context,
            metrics=state.metrics
        )

    @staticmethod
    def get_context_summary(state: ReActState) -> Dict[str, Any]:
        """Получить сводку по контексту выполнения"""
        return {
            "goal": state.goal,
            "current_step": state.current_step,
            "total_steps": len(state.steps),
            "is_completed": state.is_completed,
            "completion_reason": state.completion_reason,
            "metrics": state.metrics or {}
        }

    @staticmethod
    def should_continue(state: ReActState, max_steps: int = 10) -> bool:
        """Проверить, следует ли продолжать выполнение"""
        return not state.is_completed and len(state.steps) < max_steps