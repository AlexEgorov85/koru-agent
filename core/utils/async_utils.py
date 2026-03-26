"""
Утилиты для работы с async кодом.

Этот модуль содержит вспомогательные функции для безопасного вызова
async кода из sync контекста и других сценариев.
"""
import asyncio
from typing import Any, Coroutine, Optional


def safe_async_call(coro: Coroutine, timeout: float = 30.0) -> Any:
    """
    Безопасный вызов async coroutine из sync контекста.

    Используется когда sync метод должен вызвать async код.
    Автоматически определяет наличие running loop и использует
    соответствующий подход.

    ARGS:
    - coro: coroutine для выполнения
    - timeout: таймаут в секундах при ожидании результата

    RETURNS:
    - Результат выполнения coroutine

    RAISES:
    - asyncio.TimeoutError: если превышен таймаут
    - Exception: исключения из coroutine

    EXAMPLE:
        # Из sync метода
        def sync_method(self):
            result = safe_async_call(self.async_method())
    """
    try:
        loop = asyncio.get_running_loop()
        # Есть running loop - используем run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)
    except RuntimeError:
        # Нет running loop - создаем новый
        return asyncio.run(coro)


async def with_timeout(coro: Coroutine, timeout: float = 30.0) -> Any:
    """
    Выполнение coroutine с таймаутом.

    ARGS:
    - coro: coroutine для выполнения
    - timeout: таймаут в секундах

    RETURNS:
    - Результат выполнения coroutine

    RAISES:
    - asyncio.TimeoutError: если превышен таймаут
    """
    return await asyncio.wait_for(coro, timeout=timeout)
