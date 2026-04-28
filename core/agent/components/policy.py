"""
Политика агента.

СОДЕРЖИТ:
- AgentPolicy: единая политика агента (ограничения + retry + проверки)
- RetryPolicy: alias для обратной совместимости
"""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Any, Tuple, Optional, List

if TYPE_CHECKING:
    # Delay import to avoid circular imports
    pass


@dataclass
class PolicyVerdict:
    """Вердикт политики о допустимости действия."""
    allowed: bool
    violations: List[str] = field(default_factory=list)
    action: str = ""


class PolicyViolationError(Exception):
    """Исключение при нарушении политики."""
    
    def __init__(self, verdict: PolicyVerdict):
        self.verdict = verdict
        super().__init__(f"Policy violation: {', '.join(verdict.violations)}")


class AgentPolicy:
    """
    Единая политика агента.

    ОГРАНИЧЕНИЯ:
    - max_steps: максимальное количество шагов
    - max_errors: максимальное количество ошибок
    - max_consecutive_errors: максимум последовательных ошибок
    - max_no_progress_steps: максимум шагов без прогресса

    RETRY:
    - retry_max_attempts: максимум попыток retry
    - retry_base_delay: базовая задержка retry
    - retry_max_delay: максимальная задержка retry
    - retry_jitter: использовать jitter
    """

    def __init__(
        self,
        # Ограничения
        max_steps: int = 10,
        max_errors: int = 10,
        max_consecutive_errors: int = 3,
        max_no_progress_steps: int = 5,
        # Проверки
        max_repeated_actions: int = 3,
        max_repeated_tool_calls: int = 3,  # Новое: блокировка повторов одного инструмента (независимо от параметров)
        max_empty_results: int = 3,
        # Retry
        retry_max_attempts: int = 4,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
        retry_jitter: bool = True,
    ):
        # Ограничения
        self.max_steps = max_steps
        self.max_errors = max_errors
        self.max_consecutive_errors = max_consecutive_errors
        self.max_no_progress_steps = max_no_progress_steps

        # Проверки
        self.max_repeated_actions = max_repeated_actions
        self.max_empty_results = max_empty_results

        # Retry
        self._max_retries = retry_max_attempts  # ← Приватное поле
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.retry_jitter = retry_jitter

    @property
    def max_retries(self) -> int:
        """Alias для retry_max_attempts."""
        return self._max_retries

    @max_retries.setter
    def max_retries(self, value: int):
        """Setter для max_retries."""
        self._max_retries = value

    def get_retry_delay(self, attempt: int) -> float:
        """Рассчитать задержку перед retry."""
        delay = min(self.retry_base_delay * (2**attempt), self.retry_max_delay)
        if self.retry_jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay
    
    def evaluate(
        self,
        action_name: str,
        metrics: Any,
        state_data: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> 'PolicyVerdict':
        """
        Оценка действия политикой. Выбрасывает PolicyViolationError если действие запрещено.

        ПАРАМЕТРЫ:
        - action_name: имя планируемого действия
        - metrics: объект AgentMetrics с метриками
        - state_data: дополнительные данные состояния (опционально)
        - parameters: параметры действия (учитываются при проверке повторов)

        ВОЗВРАЩАЕТ:
        - PolicyVerdict: вердикт политики

        RAISES:
        - PolicyViolationError: если действие запрещено политикой
        """
        parameters = parameters or {}
        violations = []

        if self._check_repeat_action(action_name, metrics, parameters):
            violations.append(f"repeat_action:{action_name}")
        
        # Проверка на повторные вызовы одного инструмента (независимо от параметров)
        if self._check_repeated_tool(action_name, metrics):
            violations.append(f"repeated_tool:{action_name.split('.')[0]}")

        # Проверка на empty loop
        if self._check_empty_loop(metrics):
            violations.append("empty_loop")
        
        # Проверка на превышение ошибок
        if self._check_max_errors(metrics):
            violations.append("max_errors_reached")
        
        verdict = PolicyVerdict(
            allowed=len(violations) == 0,
            violations=violations,
            action=action_name
        )
        
        if not verdict.allowed:
            raise PolicyViolationError(verdict)
        
        return verdict
    
    def _check_repeat_action(
        self,
        action_name: str,
        metrics: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Проверка: не является ли действие повтором (с учётом параметров).
        
        ПАРАМЕТРЫ:
        - action_name: имя действия
        - metrics: объект AgentMetrics
        - parameters: параметры действия
        
        ВОЗВРАЩАЕТ:
        - True если действие повторяется слишком часто
        """
        if not hasattr(metrics, 'check_repeated_action'):
            return False
        
        is_repeat = metrics.check_repeated_action(action_name, parameters)
        
        if is_repeat and hasattr(metrics, 'repeated_actions_count'):
            return metrics.repeated_actions_count >= self.max_repeated_actions
        
        return False
    
    def _check_repeated_tool(
        self,
        action_name: str,
        metrics: Any,
    ) -> bool:
        """
        Проверка: не зациклился ли агент на одном инструменте (независимо от параметров).
        
        ЛОГИКА:
        - Сравниваем только имя инструмента (до точки)
        - Если один и тот же инструмент вызывается подряд слишком часто — блокируем
        
        ПАРАМЕТРЫ:
        - action_name: имя действия (например, check_result.generate_script)
        - metrics: объект AgentMetrics
        
        ВОЗВРАЩАЕТ:
        - True если инструмент повторяется слишком часто
        """
        if not hasattr(metrics, 'consecutive_repeated_tool'):
            return False
        
        tool_name = action_name.split('.')[0] if '.' in action_name else action_name
        return metrics.consecutive_repeated_tool >= self.max_repeated_tool_calls
    
    def _check_empty_loop(self, metrics: Any) -> bool:
        """
        Проверка: не зациклился ли агент на пустых результатах.
        
        ПАРАМЕТРЫ:
        - metrics: объект AgentMetrics
        
        ВОЗВРАЩАЕТ:
        - True если обнаружен empty loop
        """
        if not hasattr(metrics, 'empty_results_count'):
            return False
        
        return metrics.empty_results_count >= self.max_empty_results
    
    def _check_max_errors(self, metrics: Any) -> bool:
        """
        Проверка: не превышен ли лимит ошибок.
        
        ПАРАМЕТРЫ:
        - metrics: объект AgentMetrics
        
        ВОЗВРАЩАЕТ:
        - True если лимит ошибок превышен
        """
        if not hasattr(metrics, 'errors'):
            return False
        
        return len(metrics.errors) >= self.max_errors


# Alias для обратной совместимости
RetryPolicy = AgentPolicy
