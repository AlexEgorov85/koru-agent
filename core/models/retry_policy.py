from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    """
    Классификация типов ошибок для принятия решений о повторных попытках.

    КАТЕГОРИИ:
    - TRANSIENT: временные ошибки (сеть, таймауты, rate limit)
    - INVALID_INPUT: ошибки валидации входных данных (ошибки агента)
    - TOOL_FAILURE: ошибки внешних инструментов или баги
    - FATAL: критические ошибки, при которых продолжение бессмысленно

    ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
    # Сетевая ошибка
    error = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Connection timeout"
    )

    # Ошибка валидации
    error = ExecutionErrorInfo(
        category=ErrorCategory.INVALID_INPUT,
        message="Missing required parameter 'query'"
    )

    ВАЖНО:
    - Классификация ошибок критически важна для правильной стратегии повторных попыток
    - TRANSIENT ошибки обычно можно повторять
    - INVALID_INPUT ошибки обычно нельзя исправить повторными попытками
    """
    TRANSIENT = "transient"      # сеть, таймауты, rate limit
    INVALID_INPUT = "invalid_input"  # ошибка агента
    TOOL_FAILURE = "tool_failure"    # баг или внешняя система
    FATAL = "fatal"                  # продолжать бессмысленно

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

# ==========================================================
# Retry decision
# ==========================================================

class RetryDecision(str, Enum):
    """
    Возможные решения при обработке ошибки.

    РЕШЕНИЯ:
    - RETRY: повторить операцию после задержки
    - ABORT: отменить текущую операцию, но продолжить работу агента
    - FAIL: полностью прекратить выполнение

    ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
    if result.decision == RetryDecision.RETRY:
        await apply_retry_delay(result)
        # повторить операцию
    elif result.decision == RetryDecision.ABORT:
        # пропустить текущую операцию, но продолжить работу
        return ExecutionResult(status=ExecutionStatus.ABORTED)
    else:  # FAIL
        # полностью прекратить выполнение
        raise RuntimeError(f"Критическая ошибка: {result.reason}")

    СТРАТЕГИИ:
    - RETRY: для временных ошибок (сеть, таймауты)
    - ABORT: для ошибок валидации, когда действие агента некорректно
    - FAIL: для критических ошибок, делающих дальнейшую работу невозможной
    """
    RETRY = "retry"
    ABORT = "abort"
    FAIL = "fail"

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
    decision: 'RetryDecision'
    delay_seconds: float = 0.0
    reason: Optional[str] = None