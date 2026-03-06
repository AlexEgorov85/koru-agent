"""
Интерфейс для кэша.

Определяет контракт для всех реализаций кэша (Memory, Redis, и т.д.).
"""

from typing import Protocol, Any, Optional


class CacheInterface(Protocol):
    """
    Интерфейс для работы с кэшем.

    АБСТРАКЦИЯ: Определяет что нужно для кэширования.
    РЕАЛИЗАЦИИ: MemoryCacheProvider, RedisCacheProvider.
    """

    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - Значение или None если не найдено
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Сохранить значение в кэш.

        ARGS:
        - key: Ключ кэша
        - value: Значение
        - ttl: Время жизни в секундах (None = по умолчанию)
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        Удалить значение из кэша.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - True если ключ существовал
        """
        ...

    async def exists(self, key: str) -> bool:
        """
        Проверить наличие ключа в кэше.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - True если ключ существует
        """
        ...

    async def clear(self) -> None:
        """Очистить весь кэш."""
        ...

    @property
    def stats(self) -> dict:
        """Получить статистику кэша."""
        ...
