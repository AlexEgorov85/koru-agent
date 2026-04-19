"""Состояние цикла агента (state) для управления поведением ReAct.

АРХИТЕКТУРА:
- Хранит агрегированное состояние сессии, влияющее на следующие шаги.
- Не содержит тяжёлых ресурсов и инфраструктурных зависимостей.
- Используется как источник правды для policy/reflection/prompt.

ВАЖНО:
- Здесь разделены total-метрики и consecutive-метрики.
- Для stop/policy решений используются именно consecutive значения,
  чтобы случайные разовые пустые ответы не «ломали» сессию.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """Состояние выполнения агентного цикла."""

    step_number: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)

    # История ошибок (человеко-читаемые маркеры для промпта/логики)
    errors: List[str] = field(default_factory=list)

    # TOTAL метрики
    total_empty_results: int = 0

    # CONSECUTIVE метрики (для policy/stop решений)
    consecutive_empty_results: int = 0
    consecutive_repeated_actions: int = 0

    # Поля обратной совместимости (используются в текущих местах кода/промптов)
    empty_results_count: int = 0
    repeated_actions_count: int = 0

    last_action: Optional[str] = None
    last_action_signature: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None

    def add_step(
        self,
        action_name: str,
        status: str,
        parameters: Optional[Dict[str, Any]] = None,
        observation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Добавить запись шага и обновить счётчики повторов.

        ЛОГИКА ПОВТОРОВ:
        - Сравниваем не только action_name, но и action_signature
          (action + нормализованные параметры).
        - Это снижает ложные блокировки, когда один и тот же инструмент
          вызывается с разными входными параметрами.
        """
        self.step_number += 1
        action_signature = self.build_action_signature(
            action_name=action_name, parameters=parameters
        )

        if self.last_action_signature == action_signature:
            self.consecutive_repeated_actions += 1
        else:
            self.consecutive_repeated_actions = 0

        self.last_action = action_name
        self.last_action_signature = action_signature
        self.last_observation = observation

        # Поле совместимости для уже существующей логики.
        self.repeated_actions_count = self.consecutive_repeated_actions

        self.history.append(
            {
                "step": self.step_number,
                "action": action_name,
                "action_signature": action_signature,
                "status": status,
                "parameters": parameters or {},
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
            self.total_empty_results += 1
            self.consecutive_empty_results += 1
            self.empty_results_count = self.consecutive_empty_results
        elif obs_status == "error":
            self.errors.append(
                f"OBSERVATION:{observation.get('insight', 'unknown_error')}"
            )
            self.consecutive_empty_results = 0
            self.empty_results_count = self.consecutive_empty_results
        else:
            # Любой непустой и неошибочный ответ разрывает streak пустых результатов.
            self.consecutive_empty_results = 0
            self.empty_results_count = self.consecutive_empty_results

        quality = str(observation.get("quality", "")).lower()
        if quality == "useless":
            self.errors.append("OBSERVATION:USELESS_RESULT")

    def get_recent_actions(self, limit: int = 3) -> List[str]:
        """Получить последние действия по истории шагов."""
        recent = self.history[-limit:]
        return [str(step.get("action", "")) for step in recent if step.get("action")]

    def get_recent_action_signatures(self, limit: int = 3) -> List[str]:
        """Получить последние action_signature для policy-проверок."""
        recent = self.history[-limit:]
        return [
            str(step.get("action_signature", ""))
            for step in recent
            if step.get("action_signature")
        ]

    def build_action_signature(
        self, action_name: str, parameters: Optional[Dict[str, Any]]
    ) -> str:
        """Построить стабильную сигнатуру действия для сравнения повторов."""
        normalized_params = parameters or {}
        return f"{action_name}|{self._stable_serialize(normalized_params)}"

    def _stable_serialize(self, value: Any) -> str:
        """Стабильная сериализация словаря/списка для сравнения сигнатур."""
        if isinstance(value, dict):
            items = []
            for key in sorted(value.keys()):
                items.append(f"{key}:{self._stable_serialize(value[key])}")
            return "{" + ",".join(items) + "}"
        if isinstance(value, list):
            return "[" + ",".join([self._stable_serialize(v) for v in value]) + "]"
        return str(value)
