"""
RetryPolicy — параметры для network retry.

АРХИТЕКТУРА (Этап 4):
- ТОЛЬКО параметры: max_retries, delays
- БЕЗ decision logic: evaluate(), should_fallback(), detect_loop()
- Pattern сам решает когда retry/stop/fail

ОТВЕТСТВЕННОСТЬ:
- Хранение параметров retry
- Расчёт задержки между попытками

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
policy = RetryPolicy(
    max_retries=3,
    base_delay=0.5,
    max_delay=5.0
)

# SafeExecutor использует для network retry
delay = policy.get_delay(attempt=0)  # → 0.5 сек
"""
import random
from typing import Optional


class RetryPolicy:
    """
    Параметры для network retry.

    ⚠️ ТОЛЬКО ДАННЫЕ: без decision logic!
    
    Pattern сам решает:
    - когда retry
    - когда stop
    - когда fail
    
    SafeExecutor использует для network retry (TRANSIENT ошибки).
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        jitter: bool = True
    ):
        """
        Инициализация параметров retry.

        ПАРАМЕТРЫ:
        - max_retries: максимальное количество попыток
        - base_delay: базовая задержка (сек)
        - max_delay: максимальная задержка (сек)
        - jitter: применять ли случайное изменение задержки
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        Рассчитать задержку перед retry.

        ФОРМУЛА:
        delay = min(base_delay * (2 ^ attempt), max_delay) + jitter

        ПАРАМЕТРЫ:
        - attempt: номер попытки (0-based)

        ВОЗВРАЩАЕТ:
        - float: задержка в секундах
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)

        if self.jitter:
            # Добавляем случайный jitter от 50% до 150%
            delay *= random.uniform(0.5, 1.5)

        return delay

    # ========================================================================
    # DEPRECATED: decision logic удалена (Этап 4)
    # ========================================================================

    # def evaluate(self, *, error: ExecutionErrorInfo, attempt: int) -> RetryResult:
    #     """⚠️ DEPRECATED: Pattern сам решает о retry."""
    #     raise NotImplementedError(
    #         "evaluate() удалён в Этапе 4. "
    #         "Pattern сам решает о retry на основе context.get_failures()."
    #     )

    # def should_fallback(self, state) -> bool:
    #     """⚠️ DEPRECATED: Pattern сам решает об остановке."""
    #     raise NotImplementedError(
    #         "should_fallback() удалён в Этапе 4. "
    #         "Pattern сам решает об остановке через DecisionType.FAIL."
    #     )

    # def should_stop_no_progress(self, state) -> bool:
    #     """⚠️ DEPRECATED: Pattern сам решает об отсутствии прогресса."""
    #     raise NotImplementedError(
    #         "should_stop_no_progress() удалён в Этапе 4. "
    #         "Pattern сам анализирует прогресс через context.has_no_progress()."
    #     )

    # def detect_loop(self, current_capability: str, last_capability: str, last_status: str) -> bool:
    #     """⚠️ DEPRECATED: Runtime детектирует зацикливание."""
    #     raise NotImplementedError(
    #         "detect_loop() удалён в Этапе 4. "
    #         "Runtime детектирует зацикливание в цикле выполнения."
    #     )
