"""
Провайдер для кэширования в памяти.

Реализация кэша в памяти с поддержкой TTL.
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta


class MemoryCacheProvider:
    """
    Провайдер кэша в памяти.

    FEATURES:
    - Хранение в оперативной памяти
    - Поддержка TTL (время жизни)
    - LRU eviction (опционально)
    - Потокобезопасность

    USAGE:
    ```python
    cache = MemoryCacheProvider(max_size=1000)

    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")
    exists = await cache.exists("key")
    await cache.delete("key")
    ```
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: Optional[int] = 3600
    ):
        """
        ARGS:
        - max_size: Максимальный размер кэша (кол-во записей)
        - default_ttl: TTL по умолчанию в секундах (None = бессрочно)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

        # Статистика
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0

    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - Значение или None если не найдено/истёк TTL
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Проверка TTL
            if entry.get("expires_at"):
                if datetime.now() > entry["expires_at"]:
                    # Истёк TTL
                    del self._cache[key]
                    self._misses += 1
                    return None

            self._hits += 1
            return entry["value"]

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
        - ttl: Время жизни в секундах (None = использовать default_ttl)
        """
        async with self._lock:
            # Проверка размера
            if len(self._cache) >= self._max_size and key not in self._cache:
                # LRU eviction: удаляем oldest entry
                await self._evict_oldest()

            # Вычисляем TTL
            actual_ttl = ttl if ttl is not None else self._default_ttl

            # Создаём запись
            entry = {
                "value": value,
                "created_at": datetime.now(),
                "expires_at": None
            }

            if actual_ttl is not None:
                entry["expires_at"] = datetime.now() + timedelta(seconds=actual_ttl)

            self._cache[key] = entry
            self._sets += 1

    async def delete(self, key: str) -> bool:
        """
        Удалить значение из кэша.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - True если ключ существовал
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._deletes += 1
                return True
            return False

    async def exists(self, key: str) -> bool:
        """
        Проверить наличие ключа в кэше.

        ARGS:
        - key: Ключ кэша

        RETURNS:
        - True если ключ существует и не истёк
        """
        async with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]

            # Проверка TTL
            if entry.get("expires_at"):
                if datetime.now() > entry["expires_at"]:
                    del self._cache[key]
                    return False

            return True

    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()

    async def _evict_oldest(self) -> None:
        """Удалить oldest entry (LRU eviction)."""
        if not self._cache:
            return

        # Находим oldest entry по created_at
        oldest_key = None
        oldest_time = None

        for key, entry in self._cache.items():
            created_at = entry.get("created_at")
            if oldest_time is None or (created_at and created_at < oldest_time):
                oldest_time = created_at
                oldest_key = key

        if oldest_key:
            del self._cache[oldest_key]

    @property
    def stats(self) -> Dict[str, Any]:
        """Получить статистику кэша."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "deletes": self._deletes,
            "hit_rate": hit_rate
        }

    def reset_stats(self) -> None:
        """Сбросить статистику."""
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0
