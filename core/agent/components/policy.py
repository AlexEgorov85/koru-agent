"""
Политика агента.

СОДЕРЖИТ:
- AgentPolicy: единая политика агента (ограничения + retry)
"""
import random
from typing import Optional


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


# Alias для обратной совместимости
RetryPolicy = AgentPolicy
