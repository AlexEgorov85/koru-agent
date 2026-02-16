"""
Retry & Error Policy
Назначение:
- централизовать принятие решений о retry / abort
- классифицировать ошибки execution
- исключить логику ретраев из AgentRuntime
ExecutionGateway -> ErrorPolicy -> AgentRuntime

ОСНОВНЫЕ КОМПОНЕНТЫ:
1. ErrorCategory - классификация типов ошибок
2. RetryDecision - возможные решения при ошибках
3. RetryPolicy - основная логика принятия решений
4. Вспомогательные функции для задержек

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Stateless policy: политика не хранит состояние между вызовами
- Классификация ошибок позволяет применять разные стратегии
- Экспоненциальная задержка с джиттером для избежания thundering herd
- Явное разделение ответственности: ExecutionGateway вызывает политику, но не содержит её логики

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
# Создание политики
policy = RetryPolicy(
    max_retries=3,
    base_delay=0.5,
    max_delay=5.0,
    jitter=True
)

# Информация об ошибке
error = ExecutionErrorInfo(
    category=ErrorCategory.TRANSIENT,
    message="Таймаут соединения с базой данных",
    raw_error=TimeoutError("Connection timed out")
)

# Принятие решения
result = policy.evaluate(
    error=error,
    attempt=1  # первая попытка
)

if result.decision == RetryDecision.RETRY:
    print(f"Повторная попытка через {result.delay_seconds:.2f} секунд")
    await apply_retry_delay(result)
elif result.decision == RetryDecision.ABORT:
    print(f"Отмена выполнения: {result.reason}")
else:
    print(f"Окончательный провал: {result.reason}")
"""
import random

from core.models.types.retry_policy import ExecutionErrorInfo, RetryResult
from core.models.enums.common_enums import ErrorCategory, RetryDecision


# ==========================================================
# Retry Policy
# ==========================================================

class RetryPolicy:
    """
    Stateless политика повторных попыток.
    
    НАЗНАЧЕНИЕ:
    - Принимать решения о повторных попытках на основе типа ошибки и количества попыток
    - Вычислять задержки между попытками с экспоненциальным увеличением
    - Применять джиттер для избежания синхронизации запросов
    
    ПАРАМЕТРЫ ИНИЦИАЛИЗАЦИИ:
    - max_retries: максимальное количество попыток (включая первую)
    - base_delay: базовая задержка в секундах для первой повторной попытки
    - max_delay: максимальная задержка в секундах
    - jitter: применять ли случайное изменение задержки для избежания синхронизации
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    # Создание политики с настройками по умолчанию
    default_policy = RetryPolicy()
    
    # Создание политики с кастомными настройками
    aggressive_policy = RetryPolicy(
        max_retries=5,
        base_delay=0.1,
        max_delay=2.0,
        jitter=True
    )
    
    # Использование политики
    error = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Сетевая ошибка",
        raw_error=ConnectionError("Connection refused")
    )
    
    result = aggressive_policy.evaluate(error=error, attempt=2)
    if result.decision == RetryDecision.RETRY:
        await apply_retry_delay(result)
    
    СТРАТЕГИИ ПОВЕДЕНИЯ:
    1. FATAL ошибки: немедленный FAIL без повторных попыток
    2. INVALID_INPUT ошибки: ABORT (отмена текущего действия)
    3. TRANSIENT и TOOL_FAILURE ошибки: RETRY с экспоненциальной задержкой
    4. Превышение лимита попыток: FAIL
    
    ВАЖНО:
    - Класс является stateless: не хранит состояние между вызовами
    - Все решения принимаются на основе входных параметров
    - Может быть легко заменён или расширен без изменения ExecutionGateway
    """
    
    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        jitter: bool = True,
    ):
        """
        Инициализация политики повторных попыток.
        
        ПАРАМЕТРЫ:
        - max_retries: максимальное количество попыток (по умолчанию 3)
        - base_delay: базовая задержка в секундах (по умолчанию 0.5)
        - max_delay: максимальная задержка в секундах (по умолчанию 5.0)
        - jitter: применять ли случайное изменение задержки (по умолчанию True)
        
        ПРИМЕРЫ:
        # Политика с быстрыми повторными попытками
        fast_policy = RetryPolicy(max_retries=5, base_delay=0.1, max_delay=1.0)
        
        # Консервативная политика
        conservative_policy = RetryPolicy(max_retries=2, base_delay=2.0, jitter=False)
        
        ОСОБЕННОСТИ:
        - max_retries включает первую попытку, т.е. при max_retries=3 будет максимум 3 попытки
        - base_delay используется для вычисления экспоненциальной задержки
        - jitter помогает избежать "thundering herd" проблемы при массовых сбоях
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def evaluate(
        self,
        *,
        error: ExecutionErrorInfo,
        attempt: int,
    ) -> RetryResult:
        """
        Принятие решения о повторной попытке на основе ошибки и количества попыток.
        
        АЛГОРИТМ ПРИНЯТИЯ РЕШЕНИЙ:
        1. FATAL ошибки -> FAIL
        2. INVALID_INPUT ошибки -> ABORT
        3. Проверка лимита попыток -> FAIL если превышен
        4. TRANSIENT и TOOL_FAILURE ошибки -> RETRY с экспоненциальной задержкой
        
        ПАРАМЕТРЫ:
        - error: информация об ошибке (ExecutionErrorInfo)
        - attempt: номер текущей попытки (начинается с 0)
        
        ВОЗВРАЩАЕТ:
        - RetryResult с решением и параметрами
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        policy = RetryPolicy()
        error = ExecutionErrorInfo(
            category=ErrorCategory.TRANSIENT,
            message="Таймаут соединения"
        )
        
        # Первая попытка (после первой неудачи)
        result1 = policy.evaluate(error=error, attempt=0)
        # Результат: RETRY с задержкой ~0.5 сек
        
        # Вторая попытка
        result2 = policy.evaluate(error=error, attempt=1)
        # Результат: RETRY с задержкой ~1.0 сек
        
        # Третья попытка (последняя)
        result3 = policy.evaluate(error=error, attempt=2)
        # Результат: RETRY с задержкой ~2.0 сек
        
        # Четвертая попытка (лимит превышен)
        result4 = policy.evaluate(error=error, attempt=3)
        # Результат: FAIL
        
        ВАЖНО:
        - attempt начинается с 0 (первая повторная попытка)
        - Задержка вычисляется по формуле: min(base_delay * (2 ** attempt), max_delay)
        - При включенном jitter задержка умножается на случайное число от 0.5 до 1.5
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
