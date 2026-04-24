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
    """Состояние выполнения агентного цикла.
    
    ИНКАПСУЛЯЦИЯ:
    - Все поля состояния приватные (с подчеркиванием)
    - Доступ только через методы
    - Изменение состояния только через register_step_outcome()
    """

    _step_number: int = field(default=0, repr=False)
    _history: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    _errors: List[str] = field(default_factory=list, repr=False)

    # TOTAL метрики (приватные)
    _total_empty_results: int = field(default=0, repr=False)

    # CONSECUTIVE метрики (приватные)
    _consecutive_empty_results: int = field(default=0, repr=False)
    _consecutive_repeated_actions: int = field(default=0, repr=False)

    _last_action: Optional[str] = field(default=None, repr=False)
    _last_action_signature: Optional[str] = field(default=None, repr=False)
    _last_observation: Optional[Dict[str, Any]] = field(default=None, repr=False)
    _last_corrected_params: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    # Публичные свойства только для чтения
    @property
    def step_number(self) -> int:
        return self._step_number
    
    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)  # Возвращаем копию
    
    @property
    def errors(self) -> List[str]:
        return list(self._errors)  # Возвращаем копию
    
    @property
    def total_empty_results(self) -> int:
        return self._total_empty_results
    
    @property
    def consecutive_empty_results(self) -> int:
        return self._consecutive_empty_results
    
    @property
    def consecutive_repeated_actions(self) -> int:
        return self._consecutive_repeated_actions
    
    @property
    def last_action(self) -> Optional[str]:
        return self._last_action
    
    @property
    def last_action_signature(self) -> Optional[str]:
        return self._last_action_signature
    
    @property
    def last_observation(self) -> Optional[Dict[str, Any]]:
        return self._last_observation
    
    @property
    def last_corrected_params(self) -> Optional[Dict[str, Any]]:
        return self._last_corrected_params
    
    @last_corrected_params.setter
    def last_corrected_params(self, value: Optional[Dict[str, Any]]):
        self._last_corrected_params = value

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
        self._step_number += 1
        action_signature = self.build_action_signature(
            action_name=action_name, parameters=parameters
        )

        if self._last_action_signature == action_signature:
            self._consecutive_repeated_actions += 1
        else:
            self._consecutive_repeated_actions = 0

        self._last_action = action_name
        self._last_action_signature = action_signature
        self._last_observation = observation

        self._history.append(
            {
                "step": self._step_number,
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

        self._last_observation = observation

        obs_status = str(observation.get("status", "")).lower()
        if obs_status == "empty":
            self._total_empty_results += 1
            self._consecutive_empty_results += 1
        elif obs_status == "error":
            self._errors.append(
                f"OBSERVATION:{observation.get('insight', 'unknown_error')}"
            )
            self._consecutive_empty_results = 0
        else:
            # Любой непустой и неошибочный ответ разрывает streak пустых результатов.
            self._consecutive_empty_results = 0

        quality = str(observation.get("quality", "")).lower()
        if quality == "useless":
            self._errors.append("OBSERVATION:USELESS_RESULT")

    def register_step_outcome(
        self,
        action_name: str,
        status: str,
        parameters: Optional[Dict[str, Any]] = None,
        observation: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Единый метод для регистрации исхода шага.
        
        ИНКАПСУЛЯЦИЯ:
        - Все изменения состояния проходят только через этот метод
        - Вызывается после каждого шага выполнения
        """
        # Добавляем шаг в историю
        self.add_step(
            action_name=action_name,
            status=status,
            parameters=parameters,
            observation=observation,
        )
        
        # Регистрируем observation если есть
        if observation:
            self.register_observation(observation)
        
        # Регистрируем ошибку если есть
        if error_message:
            self._errors.append(f"EXECUTION:{error_message}")

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
