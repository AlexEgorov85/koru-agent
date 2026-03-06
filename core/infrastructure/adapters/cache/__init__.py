"""
Адаптеры для CachePort.
"""
from core.infrastructure.adapters.cache.memory_cache_adapter import (
    MemoryCacheAdapter,
    RedisCacheAdapter,
)

__all__ = [
    "MemoryCacheAdapter",
    "RedisCacheAdapter",
]
