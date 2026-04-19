"""
Политика агента.

СОДЕРЖИТ:
- AgentPolicy: единая политика агента (ограничения + retry + проверки)
- RetryPolicy: alias для обратной совместимости
"""
import random
from typing import TYPE_CHECKING, Tuple, Any, Dict, List, Optional

if TYPE_CHECKING:
    # Delay import to avoid circular imports
    pass


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
    
    ПРОВЕРКИ:
    - check_repeat_action: детектирование повторов действий
    - check_empty_loop: детектирование цикла пустых результатов
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
        max_empty_results: int = 3,
        # Retry
        retry_max_attempts: int = 3,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
        retry_jitter: bool = True
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
        delay = min(self.retry_base_delay * (2 ** attempt), self.retry_max_delay)
        if self.retry_jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay
    
    def check(
        self,
        action_name: str,
        metrics: Any,
        state_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверка действия политикой.
        
        ПАРАМЕТРЫ:
        - action_name: имя планируемого действия
        - metrics: объект AgentMetrics с метриками
        - state_data: дополнительные данные состояния (опционально)
        
        ВОЗВРАЩАЕТ:
        - (allowed, reason): True если действие разрешено, иначе False + причина
        """
        # Проверка на повтор действия
        if self._check_repeat_action(action_name, metrics):
            return False, f"repeat_action:{action_name}"
        
        # Проверка на empty loop
        if self._check_empty_loop(metrics):
            return False, "empty_loop"
        
        # Проверка на превышение ошибок
        if self._check_max_errors(metrics):
            return False, "max_errors_reached"
        
        return True, None
    
    def _check_repeat_action(self, action_name: str, metrics: Any) -> bool:
        """
        Проверка: не является ли действие повтором.
        
        ПАРАМЕТРЫ:
        - action_name: имя действия
        - metrics: объект AgentMetrics
        
        ВОЗВРАЩАЕТ:
        - True если действие повторяется слишком часто
        """
        if not hasattr(metrics, 'check_repeated_action'):
            return False
        
        is_repeat = metrics.check_repeated_action(action_name)
        
        if is_repeat and hasattr(metrics, 'repeated_actions_count'):
            return metrics.repeated_actions_count >= self.max_repeated_actions
        
        return False
    
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
    
    def get_violations(
        self,
        action_name: str,
        metrics: Any
    ) -> List[str]:
        """
        Получить список всех нарушений политики.
        
        ПАРАМЕТРЫ:
        - action_name: имя действия
        - metrics: объект AgentMetrics
        
        ВОЗВРАЩАЕТ:
        - список строк с описаниями нарушений
        """
        violations = []
        
        if self._check_repeat_action(action_name, metrics):
            violations.append(f"repeat_action:{action_name}")
        
        if self._check_empty_loop(metrics):
            violations.append("empty_loop")
        
        if self._check_max_errors(metrics):
            violations.append("max_errors_reached")
        
        return violations


# Alias для обратной совместимости
RetryPolicy = AgentPolicy
