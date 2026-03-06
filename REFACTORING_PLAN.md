# 📋 План рефакторинга Agent_v5

**Дата:** 6 марта 2026  
**Текущая версия:** 5.32.0  
**Цель:** Устранение технического долга, повышение тестируемости и поддерживаемости

---

## 📊 Текущее состояние (Audit)

### Метрики кодовой базы

| Файл | Строк | Проблема | Приоритет |
|------|-------|----------|-----------|
| `core/components/base_component.py` | 1119 | Нарушение SRP | 🔴 P0 |
| `core/application/context/application_context.py` | 1564 | Нарушение SRP | 🔴 P0 |
| `core/infrastructure/context/infrastructure_context.py` | 671 | Допустимо | 🟢 P3 |
| `core/utils/lifecycle.py` | ~250 | Дублирование | 🔴 P0 |
| `core/components/lifecycle.py` | ~120 | Дублирование | 🔴 P0 |

### Архитектурные проблемы

```
❌ Нет портов (Ports & Adapters)
❌ Дублирование LifecycleManager (2 файла)
❌ BaseComponent знает об инфраструктуре
❌ Синглтоны через get_*() функции
❌ Tight coupling через ApplicationContext
```

---

## 🎯 Этап 1: Фундамент (Недели 1-2)

### 1.1. Создать порты (Ports)

**Файл:** `core/infrastructure/interfaces/ports.py`

```python
"""
Порты (интерфейсы) для архитектуры Ports & Adapters.

ПОРТЫ = Абстракции, которые определяют ЧТО нужно компоненту.
АДАПТЕРЫ = Реализации, которые определяют КАК это работает.
"""
from typing import Protocol, List, Dict, Any, Optional
from datetime import datetime


class DatabasePort(Protocol):
    """Порт для работы с базой данных."""
    
    async def query(self, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Выполнить SELECT запрос."""
        ...
    
    async def execute(self, sql: str, params: Dict[str, Any]) -> int:
        """Выполнить INSERT/UPDATE/DELETE."""
        ...
    
    async def transaction(self, operations: List[callable]) -> Any:
        """Выполнить операции в транзакции."""
        ...


class LLMPort(Protocol):
    """Порт для работы с LLM."""
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Сгенерировать ответ."""
        ...
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Сгенерировать структурированный ответ."""
        ...


class VectorPort(Protocol):
    """Порт для векторного поиска."""
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск похожих векторов."""
        ...
    
    async def add(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Добавить документы."""
        ...


class CachePort(Protocol):
    """Порт для кэширования."""
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить из кэша."""
        ...
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранить в кэш."""
        ...
    
    async def delete(self, key: str) -> bool:
        """Удалить из кэша."""
        ...


class EventPort(Protocol):
    """Порт для событий."""
    
    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Опубликовать событие."""
        ...
    
    def subscribe(self, event_type: str, handler: callable) -> None:
        """Подписаться на событие."""
        ...
```

**Адаптеры:** `core/infrastructure/adapters/`

```
adapters/
├── database/
│   ├── postgresql_adapter.py
│   └── sqlite_adapter.py
├── llm/
│   ├── vllm_adapter.py
│   ├── llama_adapter.py
│   └── openai_adapter.py
├── vector/
│   └── faiss_adapter.py
└── cache/
    └── memory_cache_adapter.py
```

---

### 1.2. Удалить дублирование Lifecycle

**Действия:**
1. ✅ Оставить `core/components/lifecycle.py` (основной)
2. ❌ Удалить `core/utils/lifecycle.py`
3. Обновить импорты во всех файлах

**Команда для поиска:**
```bash
grep -r "from core.utils.lifecycle import" core/
grep -r "from core.components.lifecycle import" core/
```

---

### 1.3. Выделить ComponentRegistry в отдельный класс

**Файл:** `core/application/registry/component_registry.py`

```python
"""
Реестр компонентов - ЕДИНОЕ место хранения всех компонентов.
"""
from typing import Dict, List, Optional, TypeVar
from core.models.enums.common_enums import ComponentType

T = TypeVar('T')

class ComponentRegistry:
    """Реестр всех компонентов прикладного контекста."""
    
    def __init__(self):
        self._components: Dict[ComponentType, Dict[str, object]] = {
            t: {} for t in ComponentType
        }
    
    def register(
        self,
        component_type: ComponentType,
        name: str,
        component: object
    ) -> None:
        """Зарегистрировать компонент."""
        if name in self._components[component_type]:
            raise ValueError(
                f"Компонент {component_type.value}.{name} уже зарегистрирован"
            )
        self._components[component_type][name] = component
    
    def get(self, component_type: ComponentType, name: str) -> Optional[object]:
        """Получить компонент по имени."""
        return self._components[component_type].get(name)
    
    def all_of_type(self, component_type: ComponentType) -> List[object]:
        """Получить все компоненты типа."""
        return list(self._components[component_type].values())
    
    def all_components(self) -> List[object]:
        """Получить все компоненты."""
        return [
            comp
            for comps in self._components.values()
            for comp in comps.values()
        ]
    
    def clear(self) -> None:
        """Очистить реестр."""
        for components in self._components.values():
            components.clear()
```

---

## 🎯 Этап 2: Decomposition ApplicationContext (Недели 3-5)

### 2.1. Выделить валидатор

**Файл:** `core/application/validation/context_validator.py`

```python
"""
Валидатор контекста - проверка состояния компонентов.
"""
from typing import List, Tuple
from core.application.registry.component_registry import ComponentRegistry


class ValidationResult:
    """Результат валидации."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class ContextValidator:
    """Валидатор состояния прикладного контекста."""
    
    def __init__(self, registry: ComponentRegistry):
        self._registry = registry
    
    def validate_all_initialized(self) -> ValidationResult:
        """Проверить, что все компоненты инициализированы."""
        result = ValidationResult()
        
        for component in self._registry.all_components():
            if hasattr(component, 'is_ready') and not component.is_ready:
                result.errors.append(
                    f"Компонент {component.name} не инициализирован"
                )
        
        return result
    
    def validate_dependencies(self) -> ValidationResult:
        """Проверить зависимости между компонентами."""
        result = ValidationResult()
        # Логика валидации зависимостей
        
        return result
```

---

### 2.2. Выделить ResourcePreloader

**Файл:** `core/application/preloading/resource_preloader.py`

```python
"""
Предзагрузчик ресурсов - загрузка промптов, контрактов, кэшей.
"""
from typing import Dict, Any, Type
from pydantic import BaseModel


class ResourcePreloader:
    """Предзагрузка ресурсов для компонентов."""
    
    def __init__(
        self,
        prompt_storage,
        contract_storage,
        cache_port
    ):
        self._prompt_storage = prompt_storage
        self._contract_storage = contract_storage
        self._cache = cache_port
    
    async def preload_prompts(
        self,
        capability_versions: Dict[str, str]
    ) -> Dict[str, Any]:
        """Предзагрузить промпты для capability."""
        # Логика загрузки из хранилища
        
    async def preload_contracts(
        self,
        contract_versions: Dict[str, str]
    ) -> Dict[str, Type[BaseModel]]:
        """Предзагрузить контракты."""
        # Логика загрузки схем
```

---

### 2.3. Рефакторинг ApplicationContext

**После:**

```python
class ApplicationContext:
    """Фасад для прикладного контекста."""
    
    def __init__(
        self,
        infrastructure_context,
        config: AppConfig,
        registry: ComponentRegistry,
        validator: ContextValidator,
        preloader: ResourcePreloader,
        profile: str = "prod"
    ):
        self._infrastructure = infrastructure_context  # Только чтение!
        self._config = config
        self._registry = registry
        self._validator = validator
        self._preloader = preloader
        self._profile = profile
    
    # Делегирование вместо реализации
    def get_skill(self, name: str):
        return self._registry.get(ComponentType.SKILL, name)
    
    def get_service(self, name: str):
        return self._registry.get(ComponentType.SERVICE, name)
```

---

## 🎯 Этап 3: Устранение tight coupling (Недели 6-7)

### 3.1. Inject портов в компоненты

**До:**
```python
class BookLibrarySkill(BaseSkill):
    async def execute(self, ...):
        db_provider = self.application_context.infrastructure_context.get_provider("default_db")
```

**После:**
```python
class BookLibrarySkill(BaseSkill):
    def __init__(
        self,
        name: str,
        db_port: DatabasePort,  # ← Внедрено!
        llm_port: LLMPort,
        executor: ActionExecutor
    ):
        super().__init__(name)
        self._db_port = db_port
        self._llm_port = llm_port
        self._executor = executor
    
    async def execute(self, ...):
        results = await self._db_port.query(sql, params)
```

---

### 3.2. Фабрика компонентов с DI

**Файл:** `core/application/factory/component_factory.py`

```python
"""
Фабрика компонентов с Dependency Injection.
"""
from core.infrastructure.interfaces.ports import DatabasePort, LLMPort
from core.application.skills.book_library_skill import BookLibrarySkill


class ComponentFactory:
    """Создание компонентов с внедрением зависимостей."""
    
    def __init__(
        self,
        db_port: DatabasePort,
        llm_port: LLMPort,
        vector_port: VectorPort,
        cache_port: CachePort
    ):
        self._db_port = db_port
        self._llm_port = llm_port
        self._vector_port = vector_port
        self._cache_port = cache_port
    
    def create_book_library_skill(
        self,
        name: str,
        config: ComponentConfig
    ) -> BookLibrarySkill:
        """Создать навык работы с библиотекой книг."""
        return BookLibrarySkill(
            name=name,
            db_port=self._db_port,
            llm_port=self._llm_port,
            executor=self._create_executor()
        )
```

---

## 🎯 Этап 4: Configuration (Недели 8-9)

### 4.1. Pydantic Settings

**Файл:** `core/config/settings.py`

```python
"""
Иерархическая конфигурация через Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Literal, Dict, Optional


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    database: str = "agent_db"
    user: str = "postgres"
    password: str = ""
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1024 <= v <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        return v
    
    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class LLMSettings(BaseSettings):
    provider: Literal["vllm", "llama", "openai", "anthropic"] = "vllm"
    model: str = "mistral-7b-instruct"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout_seconds: float = 120.0


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='AGENT_',
        env_file='.env',
        env_nested_delimiter='__'
    )
    
    profile: Literal['dev', 'prod', 'sandbox'] = 'dev'
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'DEBUG'
    
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    
    agent_max_steps: int = 10
    agent_max_retries: int = 3
```

---

## 🎯 Этап 5: Error Handling (Недели 10-11)

### 5.1. Централизованный ErrorHandler

**Файл:** `core/errors/error_handler.py`

```python
"""
Централизованная обработка ошибок с RetryPolicy.
"""
from enum import Enum
from typing import Optional, Dict, Any
import asyncio
import random


class ErrorCategory(Enum):
    TRANSIENT = "transient"      # Таймаут, сеть → retry
    INVALID_INPUT = "invalid"    # Ошибка валидации → abort
    FATAL = "fatal"              # Критическая → fail


class ErrorInfo:
    """Информация об ошибке."""
    
    def __init__(
        self,
        error: Exception,
        category: ErrorCategory,
        component: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.error = error
        self.category = category
        self.component = component
        self.operation = operation
        self.metadata = metadata or {}


class RetryPolicy:
    """Политика повторных попыток."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 0.5
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
    
    def should_retry(self, error_info: ErrorInfo, attempt: int) -> bool:
        """Проверить, нужно ли повторять."""
        if error_info.category == ErrorCategory.FATAL:
            return False
        if error_info.category == ErrorCategory.INVALID_INPUT:
            return False
        return attempt < self.max_retries
    
    def get_delay(self, attempt: int) -> float:
        """Задержка с экспоненциальным backoff и джиттером."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        return delay + random.uniform(0, self.jitter)


class ErrorHandler:
    """Централизованная обработка ошибок."""
    
    async def classify(self, error: Exception) -> ErrorCategory:
        """Классификация ошибки."""
        error_str = str(error).lower()
        
        # Транзиентные ошибки
        transient_keywords = ['timeout', 'connection', 'temporary', 'busy']
        if any(kw in error_str for kw in transient_keywords):
            return ErrorCategory.TRANSIENT
        
        # Ошибки валидации
        from core.errors.exceptions import ValidationError
        if isinstance(error, ValidationError):
            return ErrorCategory.INVALID_INPUT
        
        # Остальное - фатальное
        return ErrorCategory.FATAL
    
    async def handle(
        self,
        error: Exception,
        component: str,
        operation: str,
        retry_policy: Optional[RetryPolicy] = None
    ):
        """Обработка ошибки с retry логикой."""
        retry_policy = retry_policy or RetryPolicy()
        error_info = ErrorInfo(
            error=error,
            category=await self.classify(error),
            component=component,
            operation=operation
        )
        
        # Логирование, метрики, уведомления
        # ...
```

---

## 🎯 Этап 6: Testing (Недели 12-14)

### 6.1. Mock порты для тестов

**Файл:** `tests/mocks/ports.py`

```python
"""
Mock-порты для юнит-тестирования.
"""
from core.infrastructure.interfaces.ports import DatabasePort, LLMPort, VectorPort


class MockDatabasePort(DatabasePort):
    """Mock базы данных для тестов."""
    
    def __init__(self, predefined_results: Optional[Dict[str, Any]] = None):
        self._results = predefined_results or {}
        self._queries: List[str] = []
    
    async def query(self, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        self._queries.append(sql)
        return self._results.get(sql, [])
    
    async def execute(self, sql: str, params: Dict[str, Any]) -> int:
        self._queries.append(sql)
        return 1
    
    @property
    def queries(self) -> List[str]:
        """Получить список выполненных запросов для_assert."""
        return self._queries


class MockLLMPort(LLMPort):
    """Mock LLM для тестов."""
    
    def __init__(self, predefined_responses: Optional[List[str]] = None):
        self._responses = predefined_responses or ["Mock response"]
        self._call_count = 0
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        self._call_count += 1
        return self._responses[(self._call_count - 1) % len(self._responses)]
    
    @property
    def call_count(self) -> int:
        """Количество вызовов для assert."""
        return self._call_count
```

---

### 6.2. Пример юнит-теста

**Файл:** `tests/unit/skills/test_book_library_skill.py`

```python
"""
Юнит-тесты BookLibrarySkill с mock-портами.
"""
import pytest
from core.infrastructure.interfaces.ports import DatabasePort
from tests.mocks.ports import MockDatabasePort, MockLLMPort
from core.application.skills.book_library_skill import BookLibrarySkill


@pytest.fixture
def mock_db_port() -> DatabasePort:
    return MockDatabasePort(predefined_results={
        "SELECT * FROM books WHERE title LIKE ?": [
            {"id": 1, "title": "Test Book", "author": "Author"}
        ]
    })


@pytest.fixture
def mock_llm_port() -> LLMPort:
    return MockLLMPort(predefined_responses=["Mock analysis"])


async def test_search_books_success(
    mock_db_port: DatabasePort,
    mock_llm_port: LLMPort
):
    """Тест успешного поиска книг."""
    # Arrange
    skill = BookLibrarySkill(
        name="book_library",
        db_port=mock_db_port,
        llm_port=mock_llm_port
    )
    await skill.initialize()
    
    # Act
    result = await skill.execute(
        capability=Capability(name="search_books"),
        parameters={"query": "Test"}
    )
    
    # Assert
    assert result.success is True
    assert len(result.data["rows"]) == 1
    assert mock_db_port.queries[0].startswith("SELECT")


async def test_analyze_book_calls_llm(
    mock_db_port: DatabasePort,
    mock_llm_port: LLMPort
):
    """Тест вызова LLM для анализа."""
    skill = BookLibrarySkill(
        name="book_library",
        db_port=mock_db_port,
        llm_port=mock_llm_port
    )
    await skill.initialize()
    
    await skill.execute(
        capability=Capability(name="analyze_book"),
        parameters={"book_id": 1}
    )
    
    assert mock_llm_port.call_count == 1
```

---

## 📊 Дорожная карта

| Этап | Недели | Задачи | Критерии успеха |
|------|--------|--------|-----------------|
| **1. Фундамент** | 1-2 | Порты, Lifecycle, Registry | ✅ Нет дублирования, есть порты |
| **2. Decomposition** | 3-5 | Validator, Preloader, Registry | ✅ ApplicationContext < 300 строк |
| **3. DI** | 6-7 | Фабрики, Injection | ✅ Нет `infrastructure_context` в skills |
| **4. Configuration** | 8-9 | Pydantic Settings | ✅ 1 источник истины |
| **5. Error Handling** | 10-11 | ErrorHandler, RetryPolicy | ✅ Централизованная обработка |
| **6. Testing** | 12-14 | Mock-порты, тесты | ✅ 80% coverage, < 30 сек |

---

## ✅ Критерии завершения

```bash
# 1. Тесты без инфраструктуры
pytest tests/unit/  # ✅ < 30 секунд

# 2. mypy без ошибок
mypy core/  # ✅ 0 errors

# 3. Нет прямых импортов инфраструктуры
grep -r "infrastructure_context" core/application/  # ✅ 0 matches

# 4. Нет синглтонов
grep -r "get_event_bus()" core/  # ✅ Только в composition root

# 5. Нет дублирования
grep -r "LifecycleManager" core/  # ✅ 1 файл

# 6. SRP соблюдён
wc -l core/components/base_component.py  # ✅ < 300
wc -l core/application/context/application_context.py  # ✅ < 300
```

---

## 🚀 Быстрые победы (можно сделать за 1 день)

1. **Удалить `core/utils/lifecycle.py`** → перенести импорты
2. **Создать `core/infrastructure/interfaces/ports.py`** → определить 5 портов
3. **Создать `tests/mocks/ports.py`** → mock-реализации
4. **Написать 5 юнит-тестов** → показать тестируемость

---

## 📚 Ресурсы

- [Clean Architecture (Robert Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Ports & Adapters (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Dependency Injection in Python](https://realpython.com/dependency-injection-python/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
