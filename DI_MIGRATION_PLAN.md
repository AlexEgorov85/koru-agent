# План миграции на интерфейсы и внедрение зависимостей (DI)

## 🎯 Цель

Полностью отказаться от прямых зависимостей компонентов от контекстов (`ApplicationContext`, `InfrastructureContext`) и перейти на **внедрение зависимостей через интерфейсы**.

### Текущая проблема

```python
# ❌ СЕЙЧАС: Компоненты зависят от контекстов
class BookLibrarySkill(BaseComponent):
    def __init__(self, name, application_context, component_config, executor):
        self.application_context = application_context  # ← Прямая зависимость
        
    async def _search_books_dynamic(self, params):
        # Получаем провайдеры через контекст
        db = self.application_context.infrastructure_context.db_provider_factory.get_provider("default_db")
        llm = self.application_context.infrastructure_context.llm_provider_factory.get_provider("default_llm")
```

### Целевое состояние

```python
# ✅ БУДЕТ: Компоненты зависят только от интерфейсов
class BookLibrarySkill(BaseComponent):
    def __init__(
        self, 
        name, 
        component_config, 
        executor,
        db: DatabaseInterface,      # ← Внедрение через интерфейс
        llm: LLMInterface,          # ← Внедрение через интерфейс
        cache: CacheInterface       # ← Внедрение через интерфейс
    ):
        self._db = db
        self._llm = llm
        self._cache = cache
        
    async def _search_books_dynamic(self, params):
        # Используем внедрённые зависимости
        result = await self._db.query("SELECT * FROM books")
```

---

## 📋 Этапы миграции

### Этап 1: Подготовка инфраструктуры DI

#### 1.1 Создать контейнер зависимостей

**Файл:** `core/di/container.py`

```python
"""
Контейнер для внедрения зависимостей.

RESPONSIBILITIES:
- Регистрация провайдеров по интерфейсам
- Разрешение зависимостей
- Управление временем жизни (singleton, transient, scoped)
"""
from typing import Dict, Type, Any, Optional, Callable
from core.interfaces import DatabaseInterface, LLMInterface, CacheInterface

class DependencyContainer:
    """DI контейнер для управления зависимостями."""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
    
    def register_singleton(self, interface: Type, implementation: Any):
        """Зарегистрировать singleton реализацию интерфейса."""
        self._services[interface] = implementation
    
    def register_factory(self, interface: Type, factory: Callable):
        """Зарегистрировать фабрику для создания экземпляров."""
        self._factories[interface] = factory
    
    def resolve(self, interface: Type) -> Any:
        """Получить реализацию интерфейса."""
        if interface in self._services:
            return self._services[interface]
        if interface in self._factories:
            factory = self._factories[interface]
            return factory()
        raise ValueError(f"No registration for {interface}")
```

#### 1.2 Создать декоратор для автоматического DI

**Файл:** `core/di/inject.py`

```python
"""
Декораторы для автоматического внедрения зависимостей.
"""
from typing import Type, Any, get_type_hints
from functools import wraps

def inject(func):
    """
    Декоратор для автоматического внедрения зависимостей.
    
    USAGE:
    ```python
    @inject
    def create_skill(db: DatabaseInterface, llm: LLMInterface):
        return MySkill(db=db, llm=llm)
    ```
    """
    @wraps(func)
    def wrapper(container, *args, **kwargs):
        hints = get_type_hints(func)
        for param_name, param_type in hints.items():
            if param_name not in kwargs and hasattr(param_type, '__protocol_attrs__'):
                kwargs[param_name] = container.resolve(param_type)
        return func(*args, **kwargs)
    return wrapper
```

---

### Этап 2: Модификация BaseComponent

#### 2.1 Добавить поддержку внедрения зависимостей

**Файл:** `core/components/base_component.py`

```python
class BaseComponent(LifecycleMixin, ABC):
    """
    БАЗОВЫЙ КЛАСС КОМПОНЕНТА С ПОДДЕРЖКОЙ DI.
    """
    
    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: 'ActionExecutor',
        # ← НОВЫЕ ПАРАМЕТРЫ: внедрение зависимостей
        db: Optional[DatabaseInterface] = None,
        llm: Optional[LLMInterface] = None,
        cache: Optional[CacheInterface] = None,
        vector: Optional[VectorInterface] = None,
        event_bus: Optional[EventBusInterface] = None,
        prompt_storage: Optional[PromptStorageInterface] = None,
        contract_storage: Optional[ContractStorageInterface] = None,
        # ← СТАРЫЕ ПАРАМЕТРЫ (для обратной совместимости, будут удалены)
        application_context: Optional['ApplicationContext'] = None  # DEPRECATED
    ):
        self._db = db
        self._llm = llm
        self._cache = cache
        self._vector = vector
        self._event_bus = event_bus
        self._prompt_storage = prompt_storage
        self._contract_storage = contract_storage
        
        # ← DEPRECATED: для обратной совместимости
        self._application_context = application_context
        
        # ← НОВОЕ: свойство для доступа к контексту (только если не внедрены зависимости)
        @property
        def application_context(self):
            if self._application_context is None:
                raise RuntimeError(
                    "application_context is deprecated. "
                    "Use dependency injection instead."
                )
            return self._application_context
```

#### 2.2 Добавить хелперы для доступа к зависимостям

```python
class BaseComponent(LifecycleMixin, ABC):
    # ...
    
    @property
    def db(self) -> DatabaseInterface:
        """Получить DatabaseInterface."""
        if self._db is None:
            # Fallback для обратной совместимости
            return self._application_context.infrastructure_context.db_provider_factory.get_provider("default_db")
        return self._db
    
    @property
    def llm(self) -> LLMInterface:
        """Получить LLMInterface."""
        if self._llm is None:
            return self._application_context.infrastructure_context.llm_provider_factory.get_provider("default_llm")
        return self._llm
    
    # Аналогично для cache, vector, event_bus, etc.
```

---

### Этап 3: Обновление ComponentFactory

#### 3.1 Модифицировать фабрику для внедрения зависимостей

**Файл:** `core/application/components/component_factory.py`

```python
class ComponentFactory:
    """Фабрика компонентов с поддержкой DI."""
    
    def __init__(self, container: DependencyContainer):
        self._container = container
    
    async def create_and_initialize(
        self,
        component_class: Type[BaseComponent],
        name: str,
        component_config: ComponentConfig,
        executor: 'ActionExecutor'
    ) -> BaseComponent:
        """
        Создание компонента с автоматическим внедрением зависимостей.
        """
        import inspect
        
        # 1. Анализируем сигнатуру конструктора
        sig = inspect.signature(component_class.__init__)
        params = sig.parameters
        
        # 2. Формируем аргументы
        kwargs = {
            'name': name,
            'component_config': component_config,
            'executor': executor
        }
        
        # 3. Автоматически внедряем зависимости на основе аннотаций типов
        for param_name, param in params.items():
            if param_name in ['self', 'name', 'component_config', 'executor']:
                continue
            
            param_type = param.annotation
            
            # Проверяем, это ли интерфейс
            if hasattr(param_type, '__protocol_attrs__'):
                # Разрешаем зависимость через контейнер
                try:
                    kwargs[param_name] = self._container.resolve(param_type)
                except ValueError:
                    # Если не найдено в контейнере, пробуем fallback
                    kwargs[param_name] = self._resolve_fallback(param_type)
        
        # 4. Создаём компонент
        component = component_class(**kwargs)
        
        # 5. Инициализируем (без DI, только загрузка ресурсов)
        await component.initialize()
        
        return component
    
    def _resolve_fallback(self, interface_type):
        """Fallback для разрешения зависимостей из контекста."""
        # Для обратной совместимости
        pass
```

---

### Этап 4: Обновление компонентов

#### 4.1 BookLibrarySkill

**Файл:** `core/application/skills/book_library/skill.py`

```python
class BookLibrarySkill(BaseComponent):
    """Навык работы с библиотекой книг."""
    
    DEPENDENCIES = ["sql_tool", "sql_generation", "sql_query_service", "table_description_service"]
    
    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: ActionExecutor,
        # ← Внедрение зависимостей через интерфейсы
        db: DatabaseInterface,
        llm: LLMInterface,
        cache: CacheInterface,
        prompt_storage: PromptStorageInterface,
        contract_storage: ContractStorageInterface
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            db=db,
            llm=llm,
            cache=cache,
            prompt_storage=prompt_storage,
            contract_storage=contract_storage
        )
        
        # ← Используем внедрённые зависимости напрямую
        self._db = db
        self._llm = llm
        self._cache = cache
    
    async def _search_books_dynamic(self, params):
        # ← Прямое использование внедрённых зависимостей
        sql_query = await self._generate_sql_via_llm(params)
        rows = await self._db.query(sql_query)
        return SkillResult.success(data={"rows": rows})
```

#### 4.2 Обновление всех навыков

Аналогично обновить:
- `core/application/skills/data_analysis/skill.py`
- `core/application/skills/planning/skill.py`
- `core/application/skills/final_answer/skill.py`

---

### Этап 5: Обновление сервисов

#### 5.1 PromptService

**Файл:** `core/application/services/prompt_service.py`

```python
# ❌ БЫЛО
class PromptService:
    def __init__(self, application_context):
        self._context = application_context
    
    async def load_prompt(self, name: str):
        storage = self._context.infrastructure_context.prompt_storage
        return await storage.load(name)

# ✅ СТАЛО
class PromptService:
    def __init__(
        self,
        prompt_storage: PromptStorageInterface,
        cache: CacheInterface
    ):
        self._prompt_storage = prompt_storage
        self._cache = cache
    
    async def load_prompt(self, name: str):
        # Проверка кэша
        cached = await self._cache.get(f"prompt:{name}")
        if cached:
            return cached
        
        # Загрузка из хранилища
        prompt = await self._prompt_storage.load(name)
        await self._cache.set(f"prompt:{name}", prompt)
        return prompt
```

#### 5.2 ContractService

Аналогично PromptService.

---

### Этап 6: Обновление тестов

#### 6.1 Использование mock-интерфейсов

**Файл:** `tests/unit/skills/test_book_library.py`

```python
# ❌ БЫЛО
from tests.mocks.ports import MockDatabasePort, MockLLMPort

async def test_skill():
    mock_db = MockDatabasePort(...)
    mock_llm = MockLLMPort(...)
    
    # Создаём навык с моками
    skill = BookLibrarySkill(
        name="test",
        application_context=mock_context,  # ← Нужен mock контекста
        component_config=config,
        executor=mock_executor
    )
    # Затем подменяем провайдеры в контексте...

# ✅ СТАЛО
from tests.mocks.interfaces import MockDatabase, MockLLM, MockCache

async def test_skill():
    mock_db = MockDatabase(...)
    mock_llm = MockLLM(...)
    mock_cache = MockCache()
    
    # Создаём навык с прямым внедрением моков
    skill = BookLibrarySkill(
        name="test",
        component_config=config,
        executor=mock_executor,
        db=mock_db,      # ← Прямое внедрение
        llm=mock_llm,    # ← Прямое внедрение
        cache=mock_cache # ← Прямое внедрение
    )
    # Никаких контекстов!
```

---

### Этап 7: Удаление устаревшего кода

#### 7.1 Удалить deprecated поля

После обновления всех компонентов:

1. Удалить `application_context` из `BaseComponent`
2. Удалить методы `get_provider()` из контекстов
3. Удалить `InfrastructureContext.get_provider()` и `ApplicationContext.get_service()`

#### 7.2 Удалить fallback-логику

Удалить код обратной совместимости из:
- `BaseComponent.db` property
- `BaseComponent.llm` property
- `ComponentFactory._resolve_fallback()`

---

## 📊 Порядок выполнения

| Этап | Задача | Файлы | Сложность |
|------|--------|-------|-----------|
| 1.1 | Создать DependencyContainer | `core/di/container.py` | Низкая |
| 1.2 | Создать @inject декоратор | `core/di/inject.py` | Низкая |
| 2.1 | Модифицировать BaseComponent | `core/components/base_component.py` | Средняя |
| 2.2 | Добавить хелперы доступа | `core/components/base_component.py` | Низкая |
| 3.1 | Обновить ComponentFactory | `core/application/components/component_factory.py` | Высокая |
| 4.1 | Обновить BookLibrarySkill | `core/application/skills/book_library/skill.py` | Средняя |
| 4.2 | Обновить остальные навыки | `core/application/skills/*/skill.py` | Средняя |
| 5.1 | Обновить PromptService | `core/application/services/prompt_service.py` | Средняя |
| 5.2 | Обновить ContractService | `core/application/services/contract_service.py` | Средняя |
| 6.1 | Обновить тесты | `tests/unit/**` | Средняя |
| 7.1 | Удалить deprecated код | Разные | Низкая |

---

## ⚠️ Риски и mitigation

| Риск | Mitigation |
|------|------------|
| Циклические зависимости | Использовать lazy injection через `Callable[[], T]` |
| Поломка существующих тестов | Сохранить fallback-логику до обновления всех тестов |
| Сложность отладки | Добавить логирование разрешения зависимостей |
| Производительность | DI контейнер - singleton, разрешение происходит 1 раз при создании компонента |

---

## ✅ Критерии завершения

- [ ] Все компоненты получают зависимости через конструктор
- [ ] Ни один компонент не обращается к `application_context.infrastructure_context`
- [ ] Все тесты используют mock-интерфейсы напрямую
- [ ] Удалены все deprecated поля и методы
- [ ] Документация обновлена

---

## 🔗 Связанные файлы

### Интерфейсы (уже созданы)
- `core/interfaces/database.py`
- `core/interfaces/llm.py`
- `core/interfaces/vector.py`
- `core/interfaces/cache.py`
- `core/interfaces/prompt_storage.py`
- `core/interfaces/contract_storage.py`
- `core/interfaces/event_bus.py`
- `core/interfaces/metrics_storage.py`
- `core/interfaces/log_storage.py`

### Провайдеры (уже обновлены)
- `core/infrastructure/providers/database/postgres_provider.py`
- `core/infrastructure/providers/llm/llama_cpp_provider.py`
- `core/infrastructure/providers/vector/faiss_provider.py`
- `core/infrastructure/providers/cache/memory_cache_provider.py`

### Mock-интерфейсы (уже созданы)
- `tests/mocks/interfaces.py`

---

*План создан: 2026-03-06*
