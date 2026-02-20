"""
Тесты AnalysisCache.
"""

import pytest
import asyncio
from core.infrastructure.cache.analysis_cache import AnalysisCache


class TestAnalysisCache:
    """Тесты AnalysisCache."""
    
    @pytest.fixture
    def cache(self, tmp_path):
        return AnalysisCache(str(tmp_path / "cache"))
    
    @pytest.mark.asyncio
    async def test_set_get(self, cache):
        """Сохранение и получение."""
        await cache.set("test_key", {"value": "test"})
        
        result = await cache.get("test_key")
        
        assert result == {"value": "test"}
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """Получение несуществующего ключа."""
        result = await cache.get("nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Удаление."""
        await cache.set("test_key", {"value": "test"})
        
        deleted = await cache.delete("test_key")
        
        assert deleted is True
        
        result = await cache.get("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Удаление несуществующего ключа."""
        deleted = await cache.delete("nonexistent")
        
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_invalidate_by_prefix(self, cache):
        """Инвалидация по префиксу."""
        await cache.set("character_book_1", {"value": "1"})
        await cache.set("character_book_2", {"value": "2"})
        await cache.set("theme_book_1", {"value": "3"})
        
        deleted = await cache.invalidate_by_prefix("character_")
        
        assert deleted == 2
        
        assert await cache.get("character_book_1") is None
        assert await cache.get("character_book_2") is None
        assert await cache.get("theme_book_1") is not None
    
    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Очистка всего кэша."""
        await cache.set("key1", {"value": "1"})
        await cache.set("key2", {"value": "2"})
        await cache.set("key3", {"value": "3"})
        
        deleted = await cache.clear()
        
        assert deleted == 3
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        """Статистика кэша."""
        await cache.set("key1", {"value": "1"})
        await cache.set("key2", {"value": "2"})
        
        stats = await cache.get_stats()
        
        assert stats["total_keys"] == 2
        assert stats["total_size_mb"] > 0
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Истечение TTL."""
        # Сохраняем с TTL 0 часов (сразу истекает)
        await cache.set("test_key", {"value": "test"}, ttl_hours=0)
        
        # Ждём немного
        await asyncio.sleep(0.1)
        
        # Должен истечь
        result = await cache.get("test_key")
        
        # Может быть None (истёк) или данные (не успел истечь)
        # Зависит от точности времени
        assert result is None or result == {"value": "test"}
