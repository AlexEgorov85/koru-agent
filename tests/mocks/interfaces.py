"""
Mock-интерфейсы для юнит-тестирования.

ИСПОЛЬЗОВАНИЕ:
```python
from tests.mocks.interfaces import MockDatabase, MockLLM

async def test_skill():
    db = MockDatabase(predefined_results={...})
    llm = MockLLM(predefined_responses=[...])

    skill = PlanningSkill(db=db, llm=llm)
    result = await skill.execute(...)

    # Assert
    assert db.queries_executed == [...]
    assert llm.call_count == 1
```
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

from core.infrastructure.interfaces import (
    DatabaseInterface,
    LLMInterface,
    VectorInterface,
    CacheInterface,
    EventBusInterface,
    MetricsStorageInterface,
    LogStorageInterface,
)


class PromptStorageInterface:
    """Mock PromptStorageInterface — placeholder."""
    pass


class ContractStorageInterface:
    """Mock ContractStorageInterface — placeholder."""
    pass


class MockDatabase(DatabaseInterface):
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

    async def transaction(self):
        if self._should_fail:
            raise ConnectionError("Mock transaction failed")

        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def _transaction():
            try:
                yield self
            except Exception as e:
                raise

        return _transaction()

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


class MockLLM(LLMInterface):
    """
    Mock LLM для тестов.

    FEATURES:
    - Предопределённые ответы по промптам (точное совпадение или contains)
    - Подсчёт вызовов
    - Симуляция задержки
    - history промптов для debug

    ИСПОЛЬЗОВАНИЕ:
    ```python
    mock_llm = MockLLM()
    mock_llm.register_response("сколько", "В 2025 году было 10 проверок")
    mock_llm.register_response(" ReasoningResult", '{"stop_condition": false, "decision": {"next_action": "check_result.generate_script"}}')

    # Или автоответ по ключевым словам
    mock_llm.set_default_response('{"answer": "default"}')
    ```
    """

    def __init__(
        self,
        predefined_responses: Optional[Dict[str, str]] = None,
        delay_seconds: float = 0.0,
        should_fail: bool = False,
        default_response: str = "Mock LLM response"
    ):
        """
        ARGS:
        - predefined_responses: Словарь {ключ_в_промпте: ответ}
        - delay_seconds: Имитация задержки ответа
        - should_fail: Симулировать ошибку
        - default_response: Ответ по умолчанию если не найден по ключу
        """
        import asyncio

        self._asyncio = asyncio
        self._responses = predefined_responses or {}
        self._default_response = default_response
        self._delay = delay_seconds
        self._should_fail = should_fail
        self._call_count = 0
        self._prompt_history: List[str] = []

    def register_response(self, prompt_contains: str, response: str) -> None:
        """Зарегистрировать ответ для промпта содержащего prompt_contains."""
        self._responses[prompt_contains] = response

    def set_default_response(self, response: str) -> None:
        """Установить ответ по умолчанию."""
        self._default_response = response

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Сгенерировать текстовый ответ."""
        if self._should_fail:
            raise TimeoutError("Mock LLM timeout")

        if self._delay > 0:
            await self._asyncio.sleep(self._delay)

        self._call_count += 1
        self._prompt_history.append(prompt)

        response = self._find_response(prompt)
        return response

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Сгенерировать структурированный ответ (JSON)."""
        if self._should_fail:
            raise TimeoutError("Mock LLM timeout")

        self._call_count += 1
        self._prompt_history.append(prompt)

        full_prompt = f"{prompt} {response_schema}"
        response_text = self._find_response(full_prompt)

        try:
            import json
            return json.loads(response_text)
        except json.JSONDecodeError:
            return self._mock_structured_response(response_schema)

    async def health_check(self) -> "LLMHealthStatus":
        """Проверка здоровья LLM."""
        from core.models.types.llm_types import LLMHealthStatus
        return LLMHealthStatus.HEALTHY

    def _find_response(self, prompt: str) -> str:
        """Найти ответ по ключевой фразе в промпте."""
        for key, response in self._responses.items():
            if key in prompt:
                return response
        return self._default_response

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
    def prompt_history(self) -> List[str]:
        """История промптов для assert."""
        return self._prompt_history

def reset(self) -> None:
        """Сбросить состояние для следующего теста."""
        self._call_count = 0
        self._prompt_history.clear()


def create_audit_mock_llm() -> MockLLM:
    """
    Фабрика: MockLLM с реалистичными ответами для аудиторских тестов.

    RESPONSES:
    - ReasoningResult → решения ReAct (decision с next_action)
    - SQLGenerationOutput → сгенерированный SQL
    - final_answer.generate → финальный ответ

    RESPONSES из llm_responses.py:
    """
    from tests.mocks.llm_responses import (
        DEFAULT_MOCK_RESPONSES,
        REASONING_EMPTY_CONTEXT,
        SQL_COUNT_CHECKS,
        REASONING_EMPTY_RESULTS,
        FINAL_ANSWER_DEFAULT,
    )

    mock = MockLLM()

    mock.register_response(" ReasoningResult", REASONING_EMPTY_CONTEXT)
    mock.register_response("SQLGenerationOutput", SQL_COUNT_CHECKS)
    mock.register_response("final_answer.generate", FINAL_ANSWER_DEFAULT)

    mock.set_default_response('{"answer": "Mock response"}')
    return mock


class MockVector(VectorInterface):
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


class MockCache(CacheInterface):
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


class MockEventBus(EventBusInterface):
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


# Placeholder для остальных mock-интерфейсов
class MockPromptStorage(PromptStorageInterface):
    """Mock хранилища промптов для тестов."""
    pass


class MockContractStorage(ContractStorageInterface):
    """Mock хранилища контрактов для тестов."""
    pass


class MockMetricsStorage(MetricsStorageInterface):
    """Mock хранилища метрик для тестов."""
    pass


class MockLogStorage(LogStorageInterface):
    """Mock хранилища логов для тестов."""
    pass
