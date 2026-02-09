
import asyncio
from src.domain.retry_policy import RetryDecision, RetryResult


async def apply_retry_delay(result: RetryResult):
    """
    Асинхронная задержка перед повторной попыткой.
    
    НАЗНАЧЕНИЕ:
    - Реализует задержку, если решение было RETRY
    - Безопасно игнорирует другие типы решений
    - Предоставляет тестабельный интерфейс (можно замокать в тестах)
    
    ПАРАМЕТРЫ:
    - result: результат принятия решения (RetryResult)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    # В основном коде
    policy = RetryPolicy()
    error = ExecutionErrorInfo(ErrorCategory.TRANSIENT, "Network error")
    result = policy.evaluate(error=error, attempt=1)
    
    if result.decision == RetryDecision.RETRY:
        await apply_retry_delay(result)
        # повторить операцию
    
    # В тестах
    with patch('retry_and_error_policy.apply_retry_delay') as mock_delay:
        await some_function_that_uses_retry()
        mock_delay.assert_called_once()
    
    ОСОБЕННОСТИ:
    - Функция ничего не делает, если decision != RETRY
    - Задержка применяется только если delay_seconds > 0
    - Асинхронная природа функции позволяет не блокировать event loop
    - Легко замокать в тестах для ускорения выполнения тестов
    """
    if result.decision == RetryDecision.RETRY and result.delay_seconds > 0:
        await asyncio.sleep(result.delay_seconds)