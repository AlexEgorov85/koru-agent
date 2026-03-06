"""
Mock-порты для юнит-тестирования.

ИСПОЛЬЗОВАНИЕ:
```python
from tests.mocks.ports import MockDatabasePort, MockLLMPort

async def test_skill():
    db_port = MockDatabasePort(predefined_results={...})
    llm_port = MockLLMPort(predefined_responses=[...])
    
    skill = BookLibrarySkill(db_port=db_port, llm_port=llm_port)
    result = await skill.execute(...)
    
    # Assert
    assert db_port.queries_executed == [...]
    assert llm_port.call_count == 1
```
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

from core.infrastructure.interfaces.ports import (
    DatabasePort,
    LLMPort,
    VectorPort,
    CachePort,
    EventPort,
    StoragePort,
    MetricsPort,
)


class MockDatabasePort(DatabasePort):
    """
    Mock базы данных для тестов.
    
    FEATURES:
    - Предопределённые результаты запросов
    - Отслеживание выполненных запросов
    - Поддержка транзакций (mock)
    """
    
    def __init__(
        self,
        predefined_results: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        should_fail: bool = False
    ):
        """
        ARGS:
        - predefined_results: {SQL-шаблон: [результаты]}
        - should_fail: Симулировать ошибку
        """
        self._results = predefined_results or {}
        self._should_fail = should_fail
        self._queries_executed: List[Dict[str, Any]] = []
        self._closed = False
    
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if self._should_fail:
            raise ConnectionError("Mock database connection failed")
        
        self._queries_executed.append({
            "type": "query",
            "sql": sql,
            "params": params
        })
        
        # Поиск по шаблону
        for pattern, result in self._results.items():
            if pattern in sql:
                return result
        
        return []
    
    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        if self._should_fail:
            raise ConnectionError("Mock database connection failed")
        
        self._queries_executed.append({
            "type": "execute",
            "sql": sql,
            "params": params
        })
        
        return 1  # Mock: 1 строка затронута
    
    async def transaction(
        self,
        operations: List[Callable[[], Awaitable[Any]]]
    ) -> Any:
        if self._should_fail:
            raise ConnectionError("Mock transaction failed")
        
        result = None
        for op in operations:
            result = await op()
        return result
    
    async def close(self) -> None:
        self._closed = True
    
    @property
    def queries_executed(self) -> List[Dict[str, Any]]:
        """Получить список выполненных запросов для assert."""
        return self._queries_executed
    
    @property
    def is_closed(self) -> bool:
        return self._closed
    
    def reset(self) -> None:
        """Сбросить состояние для следующего теста."""
        self._queries_executed.clear()
        self._closed = False


class MockLLMPort(LLMPort):
    """
    Mock LLM для тестов.
    
    FEATURES:
    - Предопределённые ответы
    - Подсчёт вызовов
    - Симуляция задержки
    """
    
    def __init__(
        self,
        predefined_responses: Optional[List[str]] = None,
        delay_seconds: float = 0.0,
        should_fail: bool = False
    ):
        """
        ARGS:
        - predefined_responses: Список ответов (циклически)
        - delay_seconds: Имитация задержки ответа
        - should_fail: Симулировать ошибку
        """
        import asyncio
        
        self._asyncio = asyncio
        self._responses = predefined_responses or ["Mock LLM response"]
        self._delay = delay_seconds
        self._should_fail = should_fail
        self._call_count = 0
        self._messages_history: List[List[Dict[str, str]]] = []
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        if self._should_fail:
            raise TimeoutError("Mock LLM timeout")
        
        if self._delay > 0:
            await self._asyncio.sleep(self._delay)
        
        self._call_count += 1
        self._messages_history.append(messages)
        
        return self._responses[(self._call_count - 1) % len(self._responses)]
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if self._should_fail:
            raise TimeoutError("Mock LLM timeout")
        
        self._call_count += 1
        self._messages_history.append(messages)
        
        # Mock: вернуть первую схему с дефолтными значениями
        return self._mock_structured_response(response_schema)
    
    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += len(msg.get("content", "").split())
        return total
    
    def _mock_structured_response(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Сгенерировать mock-ответ по схеме."""
        result = {}
        
        if "properties" in schema:
            for field_name, field_schema in schema["properties"].items():
                field_type = field_schema.get("type", "string")
                
                if field_type == "string":
                    result[field_name] = "Mock value"
                elif field_type == "integer":
                    result[field_name] = 0
                elif field_type == "boolean":
                    result[field_name] = False
                elif field_type == "array":
                    result[field_name] = []
                elif field_type == "object":
                    result[field_name] = {}
        
        return result
    
    @property
    def call_count(self) -> int:
        """Количество вызовов для assert."""
        return self._call_count
    
    @property
    def messages_history(self) -> List[List[Dict[str, str]]]:
        """История всех сообщений для assert."""
        return self._messages_history
    
    def reset(self) -> None:
        """Сбросить состояние для следующего теста."""
        self._call_count = 0
        self._messages_history.clear()


class MockVectorPort(VectorPort):
    """Mock векторного поиска для тестов."""
    
    def __init__(
        self,
        predefined_results: Optional[List[Dict[str, Any]]] = None,
        should_fail: bool = False
    ):
        self._results = predefined_results or []
        self._should_fail = should_fail
        self._documents: List[Dict[str, Any]] = []
        self._search_calls: List[Dict[str, Any]] = []
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        if self._should_fail:
            raise ConnectionError("Mock vector search failed")
        
        self._search_calls.append({
            "query": query,
            "top_k": top_k,
            "filters": filters,
            "threshold": threshold
        })
        
        return self._results[:top_k]
    
    async def add(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        if self._should_fail:
            raise ConnectionError("Mock vector add failed")
        
        ids = []
        for i, doc in enumerate(documents):
            doc_id = f"mock_{len(self._documents) + i}"
            doc["id"] = doc_id
            self._documents.append(doc)
            ids.append(doc_id)
        
        return ids
    
    async def delete(self, ids: List[str]) -> int:
        if self._should_fail:
            raise ConnectionError("Mock vector delete failed")
        
        count = 0
        for doc_id in ids:
            for i, doc in enumerate(self._documents):
                if doc.get("id") == doc_id:
                    self._documents.pop(i)
                    count += 1
                    break
        
        return count
    
    async def rebuild_index(self) -> bool:
        if self._should_fail:
            raise ConnectionError("Mock index rebuild failed")
        return True
    
    @property
    def search_calls(self) -> List[Dict[str, Any]]:
        return self._search_calls
    
    @property
    def documents(self) -> List[Dict[str, Any]]:
        return self._documents


class MockCachePort(CachePort):
    """Mock кэша для тестов."""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
        else:
            self._misses += 1
        return value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        self._cache[key] = value
    
    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        return key in self._cache
    
    async def clear(self) -> None:
        self._cache.clear()
    
    @property
    def hits(self) -> int:
        return self._hits
    
    @property
    def misses(self) -> int:
        return self._misses
    
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class MockEventPort(EventPort):
    """Mock шины событий для тестов."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._published_events: List[Dict[str, Any]] = []
    
    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        event = {
            "type": event_type,
            "payload": payload,
            "metadata": metadata or {}
        }
        self._published_events.append(event)
        
        # Вызвать подписчиков
        for pattern, handlers in self._subscribers.items():
            if pattern == "*" or pattern == event_type:
                for handler in handlers:
                    if hasattr(handler, "__await__"):
                        await handler(payload)
                    else:
                        handler(payload)
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        priority: int = 0
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
    
    async def shutdown(self) -> None:
        self._subscribers.clear()
    
    @property
    def published_events(self) -> List[Dict[str, Any]]:
        return self._published_events
    
    def reset(self) -> None:
        self._published_events.clear()
        self._subscribers.clear()


class MockStoragePort(StoragePort):
    """Mock файлового хранилища для тестов."""
    
    def __init__(self):
        self._files: Dict[str, str] = {}
    
    async def read(self, path: str, encoding: str = "utf-8") -> str:
        if path not in self._files:
            raise FileNotFoundError(f"Mock file not found: {path}")
        return self._files[path]
    
    async def write(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> None:
        self._files[path] = content
    
    async def exists(self, path: str) -> bool:
        return path in self._files
    
    async def delete(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            return True
        return False
    
    async def list_files(
        self,
        directory: str,
        pattern: Optional[str] = None
    ) -> List[str]:
        import fnmatch
        
        result = []
        for path in self._files.keys():
            if path.startswith(directory):
                if pattern is None or fnmatch.fnmatch(path, pattern):
                    result.append(path)
        
        return result


class MockMetricsPort(MetricsPort):
    """Mock сбора метрик для тестов."""
    
    def __init__(self):
        self._metrics: List[Dict[str, Any]] = []
        self._counters: Dict[str, int] = {}
    
    async def record(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        self._metrics.append({
            "name": metric_name,
            "value": value,
            "tags": tags or {},
            "timestamp": timestamp or datetime.now()
        })
    
    async def increment(
        self,
        counter_name: str,
        value: int = 1,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        key = f"{counter_name}:{tags}" if tags else counter_name
        self._counters[key] = self._counters.get(key, 0) + value
    
    async def get_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        result = []
        
        for metric in self._metrics:
            if metric["name"] != metric_name:
                continue
            
            if metric["timestamp"] < start_time:
                continue
            
            if end_time and metric["timestamp"] > end_time:
                continue
            
            if tags:
                match = all(
                    metric["tags"].get(k) == v
                    for k, v in tags.items()
                )
                if not match:
                    continue
            
            result.append(metric)
        
        return result
    
    @property
    def metrics(self) -> List[Dict[str, Any]]:
        return self._metrics
    
    @property
    def counters(self) -> Dict[str, int]:
        return self._counters
    
    def reset(self) -> None:
        self._metrics.clear()
        self._counters.clear()
