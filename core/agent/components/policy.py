"""
Политики поведения агента для новой архитектуры

ОБЪЕДИНЁННАЯ ПОЛИТИКА:
- evaluate() — решение о retry при ошибках
- should_fallback() — проверка лимита ошибок
- should_stop_no_progress() — проверка прогресса
- detect_loop() — защита от зацикливания

АРХИТЕКТУРА:
- Единый класс для всех решений агента
- Stateless политика (не хранит состояние)
- Классификация ошибок для разных стратегий
"""
import random
from typing import Optional

from core.models.types.retry_policy import ExecutionErrorInfo, RetryResult
from core.models.enums.common_enums import ErrorCategory, RetryDecision


class AgentPolicy:
    """
    Единая политика поведения агента.

    ОТВЕТСТВЕННОСТЬ:
    1. evaluate() — повторные попытки при ошибках
    2. should_fallback() — остановка при лимите ошибок
    3. should_stop_no_progress() — остановка при отсутствии прогресса
    4. detect_loop() — защита от зацикливания

    ПАРАМЕТРЫ ИНИЦИАЛИЗАЦИИ:
    - max_retries: максимальное количество попыток при ошибках (по умолчанию 3)
    - base_delay: базовая задержка в секундах (по умолчанию 0.5)
    - max_delay: максимальная задержка в секундах (по умолчанию 5.0)
    - jitter: применять ли случайное изменение задержки (по умолчанию True)
    - max_errors: лимит ошибок для остановки агента (по умолчанию 2)
    - max_no_progress_steps: лимит шагов без прогресса (по умолчанию 3)

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    # Создание политики
    policy = AgentPolicy(
        max_retries=3,
        max_errors=2,
        max_no_progress_steps=3
    )

    # Обработка ошибки
    error = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Таймаут соединения"
    )
    result = policy.evaluate(error=error, attempt=0)
    if result.decision == RetryDecision.RETRY:
        await asyncio.sleep(result.delay_seconds)
        continue

    # Проверка остановки
    if policy.should_stop_no_progress(state):
        break
    """

    def __init__(
        self,
        *,
        # Параметры retry
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        jitter: bool = True,
        # Параметры агента
        max_errors: int = 2,
        max_no_progress_steps: int = 3
    ):
        """
        Инициализация единой политики агента.

        ПАРАМЕТРЫ:
        - max_retries: максимальное количество попыток при ошибках
        - base_delay: базовая задержка (сек) для экспоненциального увеличения
        - max_delay: максимальная задержка (сек)
        - jitter: применять ли случайное изменение задержки
        - max_errors: лимит ошибок для остановки агента
        - max_no_progress_steps: лимит шагов без прогресса
        """
        # Параметры retry
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        
        # Параметры агента
        self.max_errors = max_errors
        self.max_no_progress_steps = max_no_progress_steps

    # ==========================================================
    # evaluate() — решение о retry при ошибках
    # ==========================================================

    def evaluate(
        self,
        *,
        error: ExecutionErrorInfo,
        attempt: int,
    ) -> RetryResult:
        """
        Принятие решения о повторной попытке на основе ошибки и количества попыток.

        АЛГОРИТМ ПРИНЯТИЯ РЕШЕНИЙ:
        1. FATAL ошибки → FAIL (немедленная остановка)
        2. INVALID_INPUT ошибки → ABORT (пропуск действия)
        3. Превышение лимита попыток → FAIL
        4. TRANSIENT и TOOL_FAILURE ошибки → RETRY с экспоненциальной задержкой

        ПАРАМЕТРЫ:
        - error: информация об ошибке (ExecutionErrorInfo)
        - attempt: номер текущей попытки (начинается с 0)

        ВОЗВРАЩАЕТ:
        - RetryResult с решением и параметрами

        ПРИМЕР:
        error = ExecutionErrorInfo(
            category=ErrorCategory.TRANSIENT,
            message="Таймаут соединения"
        )
        result = policy.evaluate(error=error, attempt=0)
        # → RetryDecision.RETRY с задержкой ~0.5 сек
        """
        # ---- Fatal errors ----
        if error.category == ErrorCategory.FATAL:
            return RetryResult(
                decision=RetryDecision.FAIL,
                reason="Fatal error",
            )

        # ---- Invalid agent input ----
        if error.category == ErrorCategory.INVALID_INPUT:
            return RetryResult(
                decision=RetryDecision.ABORT,
                reason="Invalid action payload",
            )

        # ---- Retry budget exceeded ----
        if attempt >= self.max_retries:
            return RetryResult(
                decision=RetryDecision.FAIL,
                reason="Retry limit exceeded",
            )

        # ---- Transient / tool errors ----
        if error.category in (ErrorCategory.TRANSIENT, ErrorCategory.TOOL_FAILURE):
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            if self.jitter:
                delay *= random.uniform(0.5, 1.5)
            return RetryResult(
                decision=RetryDecision.RETRY,
                delay_seconds=delay,
                reason="Retryable error",
            )

        # ---- Default ----
        return RetryResult(
            decision=RetryDecision.FAIL,
            reason="Unhandled error category",
        )

    # ==========================================================
    # should_fallback() / should_stop_no_progress() — остановка агента
    # ==========================================================

    def should_fallback(self, state) -> bool:
        """
        Проверка необходимости fallback.

        ПАРАМЕТРЫ:
        - state: текущее состояние агента (AgentState)

        ВОЗВРАЩАЕТ:
        - bool: True если достигнуто max_errors
        """
        return state.error_count >= self.max_errors

    def should_stop_no_progress(self, state) -> bool:
        """
        Проверка необходимости остановки из-за отсутствия прогресса.

        ПАРАМЕТРЫ:
        - state: текущее состояние агента (AgentState)

        ВОЗВРАЩАЕТ:
        - bool: True если достигнуто max_no_progress_steps
        """
        return state.no_progress_steps >= self.max_no_progress_steps

    # ==========================================================
    # detect_loop() — защита от зацикливания
    # ==========================================================

    def detect_loop(
        self,
        current_capability: str,
        last_capability: str,
        last_status: str
    ) -> bool:
        """
        Детекция зацикливания на основе повторяющихся действий.

        АРХИТЕКТУРА:
        - Если то же самое действие повторяется после успешного выполнения — это зацикливание
        - LLM не понимает, что данные уже получены и нужно вызывать final_answer.generate

        ПАРАМЕТРЫ:
        - current_capability: текущее предлагаемое действие
        - last_capability: последнее выполненное действие
        - last_status: статус последнего выполнения ('completed', 'failed', etc.)

        ВОЗВРАЩАЕТ:
        - bool: True если обнаружено зацикливание

        ПРИМЕР:
        # Зацикливание: то же действие после успешного выполнения
        policy.detect_loop(
            current_capability='book_library.execute_script',
            last_capability='book_library.execute_script',
            last_status='completed'
        )  # → True
        """
        # Зацикливание только если:
        # 1. То же самое действие
        # 2. Предыдущее выполнение было успешным (completed)
        # 3. Это не final_answer.generate (он может вызываться повторно)
        if current_capability == last_capability and last_status == 'completed':
            if current_capability != 'final_answer.generate':
                return True
        return False