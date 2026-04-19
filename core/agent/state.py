"""Состояние цикла агента (state) для управления поведением ReAct.

АРХИТЕКТУРА:
- Хранит агрегированное состояние сессии, влияющее на следующие шаги
- Не содержит тяжёлых ресурсов и инфраструктурных зависимостей
- Используется как источник правды для policy/reflection/prompt
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """Состояние выполнения агентного цикла."""

    step_number: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)
    empty_results_count: int = 0
    repeated_actions_count: int = 0

    last_action: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None

    def add_step(
        self,
        action_name: str,
        status: str,
        observation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Добавить запись шага и обновить счётчики повторов."""
        self.step_number += 1

        if self.last_action == action_name:
            self.repeated_actions_count += 1
        else:
            self.repeated_actions_count = 0

        self.last_action = action_name
        self.last_observation = observation

        self.history.append(
            {
                "step": self.step_number,
                "action": action_name,
                "status": status,
                "observation": observation,
            }
        )

    def register_observation(self, observation: Optional[Dict[str, Any]]) -> None:
        """Обновить метрики состояния на основе observation."""
        if observation is None:
            return

        self.last_observation = observation

        obs_status = str(observation.get("status", "")).lower()
        if obs_status == "empty":
            self.empty_results_count += 1
        elif obs_status == "error":
            self.errors.append(
                f"OBSERVATION:{observation.get('insight', 'unknown_error')}"
            )

        quality = str(observation.get("quality", "")).lower()
        if quality == "useless":
            self.errors.append("OBSERVATION:USELESS_RESULT")

    def get_recent_actions(self, limit: int = 3) -> List[str]:
        """Получить последние действия по истории шагов."""
        recent = self.history[-limit:]
        return [str(step.get("action", "")) for step in recent if step.get("action")]
