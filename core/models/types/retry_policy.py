from dataclasses import dataclass
from typing import Optional

from core.models.enums.common_enums import ErrorCategory, RetryDecision

@dataclass
class ExecutionErrorInfo:
    """
    Контейнер для информации об ошибке выполнения.

    ПОЛЯ:
    - category: категория ошибки (ErrorCategory)
    - message: человекочитаемое описание ошибки
    - raw_error: исходное исключение (опционально)

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    try:
        # некоторая операция
        result = await some_tool.execute(params)
    except ValueError as e:
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.INVALID_INPUT,
            message="Неверные параметры запроса",
            raw_error=e
        )
    except TimeoutError as e:
        error_info = ExecutionErrorInfo(
            category=ErrorCategory.TRANSIENT,
            message="Таймаут выполнения",
            raw_error=e
        )

    ОСОБЕННОСТИ:
    - raw_error позволяет сохранить стек вызовов для отладки
    - message должно быть человекочитаемым для логирования
    - category определяет стратегию обработки ошибки
    """
    category: 'ErrorCategory'
    message: str
    raw_error: Optional[Exception] = None

@dataclass
class RetryResult:
    """
    Результат принятия решения о повторной попытке.

    ПОЛЯ:
    - decision: решение (RetryDecision)
    - delay_seconds: задержка перед повторной попыткой в секундах
    - reason: причина принятия решения (опционально)

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    result = RetryResult(
        decision=RetryDecision.RETRY,
        delay_seconds=1.5,
        reason="Временная сетевая ошибка"
    )

    if result.decision == RetryDecision.RETRY:
        logger.info(f"Повтор через {result.delay_seconds} сек: {result.reason}")
        await asyncio.sleep(result.delay_seconds)

    ОСОБЕННОСТИ:
    - delay_seconds используется только для решения RETRY
    - reason помогает в логировании и отладке
    - все поля доступны для чтения и могут использоваться в логике вызывающего кода
    """
    decision: RetryDecision
    delay_seconds: float = 0.0
    reason: Optional[str] = None