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
from pydantic import BaseModel, Field


class ObservationAnalysis(BaseModel):
    """
    Структурированный результат анализа наблюдения.
    
    АРХИТЕКТУРА:
    - Используется как единый контракт между ObservationPhase и AgentState
    - Содержит как сырые данные, так и интерпретацию
    - Поддерживает history с лимитом 3 записи
    - Включает решение о типе сохранения (save_type)
    
    ПОЛЯ:
    - status: статус выполнения (success/error/empty)
    - quality: оценка качества данных
    - insight: ключевое наблюдение
    - hint: рекомендация для следующего шага
    - key_findings: список ключевых фактов (включая предупреждения об обрезке)
    - rule_based: был ли использован rule-based анализ
    - timestamp: время анализа
    - save_type: тип сохранения ('raw_data' или 'summary')
    """
    status: str = "unknown"
    quality: Dict[str, Any] = Field(default_factory=dict)
    insight: str = ""
    hint: str = ""
    key_findings: List[str] = Field(default_factory=list)
    rule_based: bool = False
    timestamp: Optional[str] = None
    action_name: Optional[str] = None
    step_number: Optional[int] = None
    save_type: Optional[str] = None


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
    
    # История наблюдений (лимит 3 записи) - Шаг 2.2
    _observation_history: List[ObservationAnalysis] = field(default_factory=list, repr=False)

    # TOTAL метрики (приватные)
    _total_empty_results: int = field(default=0, repr=False)

    # CONSECUTIVE метрики (приватные)
    _consecutive_empty_results: int = field(default=0, repr=False)
    _consecutive_repeated_actions: int = field(default=0, repr=False)
    _last_tool_name: Optional[str] = field(default=None, repr=False)  # Имя инструмента (без параметров)
    _consecutive_repeated_tool: int = field(default=0, repr=False)  # Счётчик повторов одного инструмента

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
    
    @property
    def observation_history(self) -> List[ObservationAnalysis]:
        """Получить копию истории наблюдений (лимит 3)."""
        return list(self._observation_history)
    
    def push_observation(self, analysis: ObservationAnalysis) -> None:
        """
        Добавить наблюдение в историю с автосдвигом старых записей.
        
        АРХИТЕКТУРА:
        - Лимит max_history=3 записи (конфигурируемо)
        - Старые записи автоматически удаляются (FIFO)
        - Шаг 2.2 плана рефакторинга
        """
        max_history = 3
        self._observation_history.append(analysis)
        
        # Автосдвиг старых записей если превышен лимит
        if len(self._observation_history) > max_history:
            self._observation_history = self._observation_history[-max_history:]

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
        
        # Проверка повтора полной сигнатуры (действие + параметры)
        if self._last_action_signature == action_signature:
            self._consecutive_repeated_actions += 1
        else:
            self._consecutive_repeated_actions = 0
        
        # Проверка повтора инструмента (независимо от параметров)
        tool_name = action_name.split('.')[0] if '.' in action_name else action_name
        if self._last_tool_name == tool_name:
            self._consecutive_repeated_tool += 1
        else:
            self._consecutive_repeated_tool = 0
        
        self._last_action = action_name
        self._last_action_signature = action_signature
        self._last_tool_name = tool_name
        self._last_observation = observation

        # Формируем текст наблюдения для быстрого доступа
        obs_text = ""
        if isinstance(observation, dict):
            insight = observation.get('insight', observation.get('observation', ''))
            key_findings = observation.get('key_findings', [])
            hint = observation.get('hint', observation.get('next_step_suggestion', ''))
        elif hasattr(observation, 'insight'):  # Pydantic ObservationAnalysis
            insight = observation.insight
            key_findings = observation.key_findings
            hint = observation.hint
        else:
            insight, key_findings, hint = "Нет анализа", [], ""

        obs_parts = [insight] if insight else []
        for finding in key_findings:
            if finding:
                obs_parts.append(f"  - {finding}")
        if hint:
            obs_parts.append(f"💡 Подсказка: {hint}")
        
        obs_text = "\n".join(obs_parts) if obs_parts else "Нет данных"
        
        self._history.append(
            {
                "step": self._step_number,
                "step_number": self._step_number,  # для надёжного поиска
                "obs_text": obs_text,  # <-- СОХРАНЯЕМ ТЕКСТ НАБЛЮДЕНИЯ ПРЯМО В STEP
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
