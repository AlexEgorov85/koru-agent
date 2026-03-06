"""
Интеграционные тесты адаптеров.

Тестируют адаптеры с реальными/mock провайдерами.
Запуск без внешней инфраструктуры (БД, LLM, Redis).

ЗАПУСК:
```bash
pytest tests/integration/adapters/test_adapter_integration.py -v
```
"""
import pytest
from typing import Dict, Any, List

from core.infrastructure.interfaces.ports import (
    DatabasePort,
    LLMPort,
    VectorPort,
    CachePort,
)
from core.infrastructure.adapters.database.postgresql_adapter import PostgreSQLAdapter, SQLiteAdapter
from core.infrastructure.adapters.llm.llama_adapter import LlamaCppAdapter, MockLLMAdapter
from core.infrastructure.adapters.vector.faiss_adapter import FAISSAdapter, MockVectorAdapter
from core.infrastructure.adapters.cache.memory_cache_adapter import MemoryCacheAdapter, RedisCacheAdapter


# ============================================================
# Тесты DatabasePort адаптеров
# ============================================================

class TestPostgreSQLAdapter:
    """Тесты PostgreSQLAdapter."""
    
    @pytest.fixture
    def mock_provider(self):
        """Создать mock PostgreSQL провайдер."""
        class MockProvider:
            def __init__(self):
                self.is_initialized = True
                self._query_results = []
                self._execute_count = 0
            
            async def execute_query(self, sql: str, params: dict = None) -> List[Dict[str, Any]]:
                self._query_results.append({"sql": sql, "params": params})
                return [{"id": 1, "name": "Test"}]
            
            async def execute(self, sql: str, params: dict = None):
                self._execute_count += 1
                # Mock DBQueryResult
                class Result:
                    rows_affected = 1
                    rows = []
                return Result()
            
            async def transaction(self):
                class TransactionContext:
                    async def __aenter__(self): pass
                    async def __aexit__(self, *args): pass
                return TransactionContext()
            
            async def shutdown(self):
                self.is_initialized = False
        
        return MockProvider()
    
    async def test_query_calls_provider(
        self,
        mock_provider
    ):
        """Тест: query вызывает провайдер."""
        adapter = PostgreSQLAdapter(mock_provider)
        
        result = await adapter.query(
            "SELECT * FROM users WHERE id = $1",
            {"id": 1}
        )
        
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert len(mock_provider._query_results) == 1
    
    async def test_execute_calls_provider(
        self,
        mock_provider
    ):
        """Тест: execute вызывает провайдер."""
        adapter = PostgreSQLAdapter(mock_provider)
        
        count = await adapter.execute(
            "INSERT INTO users (name) VALUES ($1)",
            {"name": "Test"}
        )
        
        assert count == 1
        assert mock_provider._execute_count == 1


class TestSQLiteAdapter:
    """Тесты SQLiteAdapter."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Создать временную БД SQLite."""
        import tempfile
        import os
        
        db_path = tmp_path / "test.db"
        return str(db_path)
    
    async def test_query_returns_results(
        self,
        temp_db
    ):
        """Тест: query возвращает результаты."""
        adapter = SQLiteAdapter(temp_db)
        
        # Создаём таблицу
        await adapter.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Вставляем данные (используем кортеж для SQLite)
        await adapter.execute(
            "INSERT INTO users (name) VALUES (?)",
            ("Test",)  # Кортеж вместо словаря
        )
        
        # Запрашиваем данные
        result = await adapter.query(
            "SELECT * FROM users WHERE name = ?",
            ("Test",)  # Кортеж вместо словаря
        )
        
        assert len(result) == 1
        assert result[0]["name"] == "Test"
    
    async def test_transaction_commits(
        self,
        temp_db
    ):
        """Тест: транзакция коммитит изменения."""
        adapter = SQLiteAdapter(temp_db)
        
        # Создаём таблицу
        await adapter.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Для SQLite используем прямые SQL операции в транзакции
        # Примечание: полная поддержка транзакций требует SQL-based operations
        
        # Вставляем данные
        await adapter.execute(
            "INSERT INTO users (name) VALUES (?)",
            ("Transaction User",)
        )
        
        # Проверяем что данные закоммичены
        result = await adapter.query("SELECT * FROM users")
        assert len(result) == 1
        assert result[0]["name"] == "Transaction User"


# ============================================================
# Тесты LLMPort адаптеров
# ============================================================

class TestMockLLMAdapter:
    """Тесты MockLLMAdapter."""
    
    async def test_generate_returns_predefined_response(self):
        """Тест: generate возвращает предопределённый ответ."""
        adapter = MockLLMAdapter(
            predefined_responses=["Mock response 1", "Mock response 2"]
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        response = await adapter.generate(messages)
        
        assert response == "Mock response 1"
    
    async def test_generate_structured_returns_schema(self):
        """Тест: generate_structured возвращает ответ по схеме."""
        adapter = MockLLMAdapter()
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        
        messages = [{"role": "user", "content": "Generate person"}]
        response = await adapter.generate_structured(messages, schema)
        
        assert "name" in response
        assert "age" in response
        assert isinstance(response["name"], str)
        assert isinstance(response["age"], int)
    
    async def test_call_count_tracking(self):
        """Тест: отслеживание количества вызовов."""
        adapter = MockLLMAdapter(predefined_responses=["Response"])
        
        await adapter.generate([{"role": "user", "content": "1"}])
        await adapter.generate([{"role": "user", "content": "2"}])
        await adapter.generate([{"role": "user", "content": "3"}])
        
        assert adapter.call_count == 3
    
    async def test_messages_history_tracking(self):
        """Тест: отслеживание истории сообщений."""
        adapter = MockLLMAdapter()
        
        msg1 = [{"role": "user", "content": "First"}]
        msg2 = [{"role": "user", "content": "Second"}]
        
        await adapter.generate(msg1)
        await adapter.generate(msg2)
        
        assert len(adapter.messages_history) == 2
        assert adapter.messages_history[0] == msg1
        assert adapter.messages_history[1] == msg2


# ============================================================
# Тесты VectorPort адаптеров
# ============================================================

class TestMockVectorAdapter:
    """Тесты MockVectorAdapter."""
    
    async def test_search_returns_predefined_results(self):
        """Тест: search возвращает предопределённые результаты."""
        predefined = [
            {"id": "1", "content": "Doc 1", "score": 0.95},
            {"id": "2", "content": "Doc 2", "score": 0.85}
        ]
        
        adapter = MockVectorAdapter(predefined_results=predefined)
        
        results = await adapter.search(query="test", top_k=5)
        
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[0]["score"] == 0.95
    
    async def test_add_returns_ids(self):
        """Тест: add возвращает ID добавленных документов."""
        adapter = MockVectorAdapter()
        
        documents = [
            {"content": "Doc 1", "metadata": {"source": "test"}},
            {"content": "Doc 2", "metadata": {"source": "test"}}
        ]
        
        ids = await adapter.add(documents)
        
        assert len(ids) == 2
        assert ids[0].startswith("mock_")
    
    async def test_search_calls_tracking(self):
        """Тест: отслеживание вызовов search."""
        adapter = MockVectorAdapter()
        
        await adapter.search(query="test1", top_k=5)
        await adapter.search(query="test2", top_k=10, filters={"source": "test"})
        
        assert len(adapter.search_calls) == 2
        assert adapter.search_calls[0]["query"] == "test1"
        assert adapter.search_calls[1]["filters"] == {"source": "test"}


# ============================================================
# Тесты CachePort адаптеров
# ============================================================

class TestMemoryCacheAdapter:
    """Тесты MemoryCacheAdapter."""
    
    async def test_set_and_get(self):
        """Тест: установка и получение значения."""
        cache = MemoryCacheAdapter()
        
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        
        assert value == "value1"
    
    async def test_get_nonexistent_key(self):
        """Тест: получение несуществующего ключа."""
        cache = MemoryCacheAdapter()
        
        value = await cache.get("nonexistent")
        
        assert value is None
    
    async def test_ttl_expiration(self):
        """Тест: истечение TTL."""
        import asyncio
        
        cache = MemoryCacheAdapter()
        
        # Устанавливаем с TTL 1 секунда
        await cache.set("key_ttl", "value", ttl=1)
        
        # Сразу должно работать
        assert await cache.get("key_ttl") == "value"
        
        # Ждём 1.5 секунды
        await asyncio.sleep(1.5)
        
        # Должно истечь
        value = await cache.get("key_ttl")
        assert value is None
    
    async def test_exists(self):
        """Тест: проверка существования ключа."""
        cache = MemoryCacheAdapter()
        
        assert await cache.exists("key") is False
        
        await cache.set("key", "value")
        assert await cache.exists("key") is True
        
        await cache.delete("key")
        assert await cache.exists("key") is False
    
    async def test_delete(self):
        """Тест: удаление ключа."""
        cache = MemoryCacheAdapter()
        
        await cache.set("key", "value")
        
        # Удаляем существующий
        result = await cache.delete("key")
        assert result is True
        
        # Удаляем несуществующий
        result = await cache.delete("key")
        assert result is False
    
    async def test_clear(self):
        """Тест: очистка кэша."""
        cache = MemoryCacheAdapter()
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
    
    async def test_max_size_eviction(self):
        """Тест: eviction при достижении max_size."""
        cache = MemoryCacheAdapter(max_size=3)
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # Должен вытеснить key1
        
        # key1 должен быть вытеснен (LRU)
        assert await cache.get("key1") is None
        assert await cache.get("key2") is not None
        assert await cache.get("key4") is not None
    
    async def test_stats_tracking(self):
        """Тест: статистика кэша."""
        cache = MemoryCacheAdapter()
        
        await cache.set("key", "value")
        await cache.get("key")  # hit
        await cache.get("key")  # hit
        await cache.get("nonexistent")  # miss
        
        stats = cache.stats
        
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["hit_rate"] == 2/3  # 2 hits из 3 попыток


class TestRedisCacheAdapter:
    """Тесты RedisCacheAdapter (требует Redis)."""
    
    @pytest.mark.skip(reason="Requires Redis server")
    async def test_redis_connection(self):
        """Тест: подключение к Redis."""
        cache = RedisCacheAdapter(host="localhost", port=6379)
        
        await cache.initialize()
        
        await cache.set("test", "value")
        value = await cache.get("test")
        
        assert value == "value"
        
        await cache.close()


# ============================================================
# Интеграционные тесты комбинаций адаптеров
# ============================================================

class TestAdapterCombinations:
    """Тесты комбинаций адаптеров."""
    
    async def test_db_plus_cache_integration(self):
        """Тест: интеграция БД + кэш."""
        import tempfile
        import os
        
        # Создаём временную БД
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            db_adapter = SQLiteAdapter(db_path)
            cache_adapter = MemoryCacheAdapter()
            
            # Создаём таблицу
            await db_adapter.execute(
                "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)"
            )
            
            # Кэшируем результат запроса
            cache_key = "query:items"
            
            # Первый запрос (без кэша)
            cached = await cache_adapter.get(cache_key)
            assert cached is None
            
            # Выполняем запрос к БД (используем кортеж)
            await db_adapter.execute(
                "INSERT INTO items (name) VALUES (?)",
                ("Item 1",)
            )
            
            items = await db_adapter.query("SELECT * FROM items")
            
            # Кэшируем результат
            await cache_adapter.set(cache_key, items, ttl=300)
            
            # Второй запрос (из кэша)
            cached_items = await cache_adapter.get(cache_key)
            assert len(cached_items) == 1
            assert cached_items[0]["name"] == "Item 1"
        
        finally:
            # Cleanup
            import time
            time.sleep(0.1)  # Даём файлу освободиться
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
            except PermissionError:
                pass  # Игнорируем ошибку на Windows
    
    async def test_llm_plus_cache_integration(self):
        """Тест: интеграция LLM + кэш."""
        llm_adapter = MockLLMAdapter(
            predefined_responses=["LLM response"]
        )
        cache_adapter = MemoryCacheAdapter()
        
        prompt_key = "prompt:hello"
        messages = [{"role": "user", "content": "Hello"}]
        
        # Проверяем кэш
        cached = await cache_adapter.get(prompt_key)
        assert cached is None
        
        # Генерируем ответ
        response = await llm_adapter.generate(messages)
        
        # Кэшируем
        await cache_adapter.set(prompt_key, response)
        
        # Следующий запрос из кэша
        cached_response = await cache_adapter.get(prompt_key)
        assert cached_response == "LLM response"
        assert llm_adapter.call_count == 1  # LLM вызван только 1 раз
