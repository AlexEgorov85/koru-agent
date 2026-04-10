# План миграции на единую систему `ResourceLoader`

> **Дата:** 10 апреля 2026  
> **Цель:** Убрать 4 слоя абстракции (Discovery → DataSource → Repository → Preloader) и заменить на единый `ResourceLoader`.  
> **Принцип:** «Тяжёлые ресурсы — общие. Лёгкое поведение — изолированное. Конфигурация — строго иерархическая без дублирования.»

---

## 🎯 Новая архитектура (схема потока)

```
AppConfig(profile, data_dir)
        │
        ▼
 InfrastructureContext.initialize()
        │ → создаёт ResourceLoader(profile, data_dir)
        │ → scan → parse → validate → cache
        ▼
 ComponentFactory.create_and_initialize()
        │ → loader.get_component_resources(name, component_config)
        │ → заполняет component_config.resolved_*
        ▼
 BaseComponent.initialize()
        │ → копирует resolved_* в self.prompts / self.contracts
        ▼
 Готово. Больше никаких DataRepository, ResourcePreloader, FileSystemDataSource.
```

---

## 📊 Найденные архитектурные нюансы

| Что обнаружено | Влияние на план |
|---|---|
| **`registry.yaml` не существует** | `AppConfig.from_discovery()` строит конфиги автоматически — ResourceLoader работает через discovery |
| **Двойное сканирование** | `ResourceDiscovery` (в InfraCtx) + `FileSystemDataSource` (в AppCtx) сканируют ФС независимо — ResourceLoader устраняет дублирование |
| **`DataRepository` в `core/components/services/`** | Путь отличается от изначального плана — нужно учитывать при удалении |
| **`ComponentConfig.resolved_*` типы** | Объявлены как `Dict[str, str]` / `Dict[str, Dict]`, но фактически хранят `Prompt`/`Contract` — исправим |
| **`ResourcePreloader` ленивый** | Создаётся в `ComponentFactory._get_resource_preloader()` при первом вызове — уберём |
| **`BaseComponent.initialize()`** | Копирует `resolved_*` в `self.prompts`/`self.contracts` — нужно проверить совместимость |
| **LifecycleManager** | Отдельная система регистрации компонентов, не связана с загрузкой ресурсов — не трогаем |

---

## ⚠️ Критические риски (закрыты патчами)

### 🔴 Риск 1: Двойное сканирование ФС
`AppConfig.from_discovery()` создаёт свой `ResourceLoader`, а `InfrastructureContext` → ещё один. Будет **два прохода по `data/prompts` и `data/contracts`**.

**✅ Закрытие:** `ResourceLoader` имеет кэширующий фабричный метод `get()`. И `AppConfig.from_discovery()`, и `InfrastructureContext.initialize()` вызывают `ResourceLoader.get(...)` → **0 дублирования I/O**.

### 🔴 Риск 2: `PromptService` и `ContractService` ждут `DataRepository`
После удаления репозитория они упадут с `AttributeError`.

**✅ Закрытие:** Этап 7.1 — перевести их на чтение из `component_config.resolved_*` (уже передаются в конструктор через `ComponentFactory`).

### 🔴 Риск 3: Синхронный `load_all()` в `async`-контексте
`InfrastructureContext.initialize()` — async. Вызов `load_all()` заблокирует event loop.

**✅ Закрытие:** `await asyncio.to_thread(self.resource_loader.load_all)` (Python 3.9+).

---

## 📦 Этап 1: Создание `ResourceLoader` (ядро)

**Файл:** `core/infrastructure/loading/resource_loader.py` (новый)

### Назначение

Единый загрузчик ресурсов. Заменяет:
- `ResourceDiscovery` (сканирование + кэш)
- `FileSystemDataSource` (загрузка из ФС)
- `DataRepository` (валидация + индекс)
- `ResourcePreloader` (предзагрузка для компонентов)

### API

```python
class ResourceLoader:
    """Единый загрузчик ресурсов."""

    PROFILE_STATUSES = {
        "prod": {PromptStatus.ACTIVE},
        "sandbox": {PromptStatus.ACTIVE, PromptStatus.DRAFT},
        "dev": {PromptStatus.ACTIVE, PromptStatus.DRAFT, PromptStatus.INACTIVE},
    }

    # === КЭШ НА УРОВНЕ КЛАССА (Риск 1: двойное сканирование) ===
    _cache: Dict[tuple, "ResourceLoader"] = {}

    @classmethod
    def get(cls, data_dir: Path, profile: str) -> "ResourceLoader":
        """
        Фабричный метод с кэшированием.
        Гарантирует ОДНО сканирование ФС на (data_dir, profile).
        """
        key = (data_dir.resolve(), profile)
        if key not in cls._cache:
            loader = cls(data_dir, profile)
            loader.load_all()  # Один раз сканируем
            cls._cache[key] = loader
        return cls._cache[key]

    @classmethod
    def clear_cache(cls) -> None:
        """Очистка кэша (для тестов)."""
        cls._cache.clear()

    def __init__(self, data_dir: Path, profile: str = "prod"):
        self.data_dir = data_dir.resolve()
        self.profile = profile
        self.allowed_statuses = self.PROFILE_STATUSES.get(profile, ...)
        self._prompts: Dict[tuple, Prompt] = {}       # (cap, ver) -> Prompt
        self._contracts: Dict[tuple, Contract] = {}    # (cap, ver, dir) -> Contract
        self._loaded = False

    def load_all(self) -> None:
        """Однократное сканирование, парсинг и кэширование."""

    def get_prompt(self, capability: str, version: str) -> Optional[Prompt]:
        """Получить промпт из кэша."""

    def get_contract(self, capability: str, version: str, direction: str) -> Optional[Contract]:
        """Получить контракт из кэша."""

    def get_all_prompts(self) -> List[Prompt]:
        """Все промпты из кэша (для AppConfig.from_discovery)."""

    def get_all_contracts(self) -> List[Contract]:
        """Все контракты из кэша (для AppConfig.from_discovery)."""

    def get_component_resources(
        self,
        component_name: str,
        config: ComponentConfig
    ) -> Dict[str, Any]:
        """Возвращает ресурсы, запрошенные компонентом."""
        return {
            "prompts": {...},           # Dict[str, Prompt]
            "input_contracts": {...},    # Dict[str, Contract]
            "output_contracts": {...},   # Dict[str, Contract]
        }
```

### Ключевые правила

1. **Fail-fast** — битый YAML вызывает `RuntimeError` при старте (не молчаливый skip)
2. **Фильтрация по статусу** — профиль определяет разрешённые статусы
3. **Один проход по ФС** — `load_all()` сканирует один раз, дальше только cache hits
4. **Инференция component_type** — по пути файла (как в `ResourceDiscovery._infer_component_type_from_path`)
5. **Инференция direction** — из имени файла контракта (как в `ResourceDiscovery._infer_direction_from_filename`)

---

## 🔧 Этап 2: Интеграция в `InfrastructureContext`

**Файл:** `core/infrastructure_context/infrastructure_context.py`

### Изменения

1. Добавить поле:
   ```python
   self.resource_loader: Optional[ResourceLoader] = None
   ```

2. В `initialize()` заменить **ЭТАП 3.5** (`ResourceDiscovery`):
   ```python
   # Было:
   self.resource_discovery = ResourceDiscovery(base_dir=data_dir, profile=..., event_bus=...)
   self.resource_discovery.discover_prompts()
   self.resource_discovery.discover_contracts()

   # Стало (Риск 3: async-совместимость):
   import asyncio
   self.resource_loader = ResourceLoader.get(
       data_dir=Path(self.config.data_dir),
       profile=self.config.profile
   )
   await asyncio.to_thread(self.resource_loader.load_all)  # Не блокирует event loop
   ```

   > **Примечание:** `ResourceLoader.get()` гарантирует, что сканирование произойдёт только один раз.
   > Если `AppConfig.from_discovery()` уже вызывал `ResourceLoader.get()` с теми же параметрами,
   > `load_all()` будет no-op (флаг `_loaded` защитит от повторного сканирования).

3. Убрать `self.resource_discovery`
4. Убрать импорт `ResourceDiscovery`

---

## 🏗️ Этап 3: Обновление `ComponentFactory`

**Файл:** `core/agent/components/component_factory.py`

### Изменения

1. `__init__` — принимать `resource_loader` из `InfrastructureContext`:
   ```python
   def __init__(self, infrastructure_context: InfrastructureContext):
       self._infrastructure_context = infrastructure_context
       self.event_bus = infrastructure_context.event_bus
       self._resource_loader = infrastructure_context.resource_loader
   ```

2. **Удалить** `_get_resource_preloader()` и `self._resource_preloader`

3. В `create_and_initialize()` заменить блок предзагрузки:
   ```python
   # Было:
   preloader = self._get_resource_preloader(application_context)
   resources = await preloader.preload_for_component(name, component_config)

   # Стало (loader уже отсканирован в InfraCtx, берём из кэша):
   resources = self._resource_loader.get_component_resources(name, component_config)
   ```

4. Заполнение `resolved_*` остаётся тем же:
   ```python
   component_config.resolved_prompts = resources["prompts"]
   component_config.resolved_input_contracts = resources["input_contracts"]
   component_config.resolved_output_contracts = resources["output_contracts"]
   ```

---

## 📝 Этап 4: Исправление типов в `ComponentConfig`

**Файл:** `core/config/component_config.py`

### Изменения

```python
# Импорты
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract

# Было:
resolved_prompts: Dict[str, str] = Field(default_factory=dict)
resolved_input_contracts: Dict[str, Dict] = Field(default_factory=dict)
resolved_output_contracts: Dict[str, Dict] = Field(default_factory=dict)

# Стало:
resolved_prompts: Dict[str, Prompt] = Field(default_factory=dict)
resolved_input_contracts: Dict[str, Contract] = Field(default_factory=dict)
resolved_output_contracts: Dict[str, Contract] = Field(default_factory=dict)
```

---

## 🗃️ Этап 5: Обновление `ApplicationContext`

**Файл:** `core/application_context/application_context.py`

### Изменения

1. **Убрать** создание `FileSystemDataSource` + `DataRepository` в `initialize()`:
   ```python
   # Удалить весь блок:
   # if not self.data_repository:
   #     from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
   #     discovery = self.infrastructure_context.get_resource_discovery()
   #     registry_config = {...}
   #     fs_data_source = FileSystemDataSource(self._data_dir, registry_config)
   #     fs_data_source.initialize()
   #     self.data_repository = DataRepository(...)
   # if not await self.data_repository.initialize(self.config):
   #     ...
   ```

2. **Удалить** `self.data_repository = None` и все `await self.data_repository.*` вызовы

3. Убрать импорт `DataRepository` и `FileSystemDataSource`

4. **Убрать** `_auto_fill_config()` если он зависит от `data_repository`

---

## 🔄 Этап 6: Обновление `AppConfig.from_discovery()`

**Файл:** `core/config/app_config.py`

### Изменения

1. Заменить `ResourceDiscovery` на `ResourceLoader`:
   ```python
   # Было:
   discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)
   prompts = discovery.discover_prompts()
   contracts = discovery.discover_contracts()

   # Стало:
   loader = ResourceLoader(data_dir=Path(data_dir), profile=profile)
   loader.load_all()
   # Получаем все промпты и контракты из loader
   prompts = loader._prompts_cache.values()  # или добавить публичный метод get_all_prompts()
   contracts = loader._contracts_cache.values()  # или get_all_contracts()
   ```

2. Добавить публичные методы в `ResourceLoader`:
   ```python
   def get_all_prompts(self) -> List[Prompt]:
       return list(self._prompts.values())

   def get_all_contracts(self) -> List[Contract]:
       return list(self._contracts.values())
   ```

---

### 🔧 Этап 7.1: Миграция `PromptService` / `ContractService` (Риск 2)

Эти сервисы сейчас читают из `DataRepository`. После удаления — перейдут на `component_config.resolved_*`.

#### `PromptService`

**Файл:** Найти через grep (вероятно `core/components/services/prompt_service.py`)

```python
# Было:
def get_prompt(self, capability: str) -> str:
    prompt = self._data_repository.get_prompt(capability, version)
    return prompt.content

# Стало:
def __init__(self, component_config: ComponentConfig, ...):
    self._config = component_config
    # resolved_prompts уже Dict[str, Prompt] — берём напрямую

def get_prompt(self, capability: str) -> str:
    prompt = self._config.resolved_prompts.get(capability)
    if not prompt:
        raise ValueError(f"Промпт '{capability}' не загружен! Проверьте YAML в data/prompts/")
    return prompt.content
```

#### `ContractService`

**Файл:** Найти через grep (вероятно `core/components/services/contract_service.py`)

```python
# Было:
contract = self._data_repository.get_contract(cap, ver, direction)

# Стало:
def get_input_contract(self, capability: str) -> Contract:
    contract = self._config.resolved_input_contracts.get(capability)
    if not contract:
        raise ValueError(f"Входной контракт '{capability}' не загружен!")
    return contract

def get_output_contract(self, capability: str) -> Contract:
    contract = self._config.resolved_output_contracts.get(capability)
    if not contract:
        raise ValueError(f"Выходной контракт '{capability}' не загружен!")
    return contract
```

> **Важно:** NO FALLBACK — если ресурс указан в конфиге, но не найден → `ValueError` сразу.

---

## 🔗 Этап 7: Найти и обновить все ссылки

### Файлы, ссылающиеся на удаляемые классы

| Файл | Ссылается на | Действие |
|---|---|---|
| `core/infrastructure/discovery/resource_discovery.py` | Сам удаляемый | 🗑️ Удалить |
| `core/infrastructure/storage/resource_data_source.py` | Сам удаляемый | 🗑️ Удалить |
| `core/infrastructure/storage/file_system_data_source.py` | Сам удаляемый | 🗑️ Удалить |
| `core/components/services/data_repository.py` | Сам удаляемый | 🗑️ Удалить |
| `core/components/services/preloading/resource_preloader.py` | Сам удаляемый | 🗑️ Удалить |
| `core/agent/components/component_factory.py` | `ResourcePreloader` | ✅ Обновить (Этап 3) |
| `core/application_context/application_context.py` | `DataRepository`, `FileSystemDataSource` | ✅ Обновить (Этап 5) |
| `core/config/app_config.py` | `ResourceDiscovery` | ✅ Обновить (Этап 6) |
| `core/infrastructure_context/infrastructure_context.py` | `ResourceDiscovery` | ✅ Обновить (Этап 2) |
| `core/config/component_config.py` | Типы `resolved_*` | ✅ Обновить (Этап 4) |
| `core/components/services/base_component.py` | `ResourcePreloader` | 🔍 Проверить |
| `core/components/services/prompt_service.py` | `DataRepository` | 🔍 Проверить |
| `core/components/services/contract_service.py` | `DataRepository` | 🔍 Проверить |
| `scripts/.../dynamic_loader.py` | `ResourceDiscovery` | 🔍 Проверить |
| `diagnose_sql.py` | `ResourceDiscovery` | 🔍 Проверить |
| `scripts/.../version_promoter.py` | `FileSystemDataSource` | 🔍 Проверить |
| `tests/...` | Разные | 🔍 Проверить |

---

## 🗑️ Этап 8: Удаление легаси

| Файл | Причина удаления |
|---|---|
| `core/infrastructure/discovery/resource_discovery.py` | Логика сканирования перенесена в `ResourceLoader._scan_dir()` |
| `core/infrastructure/storage/resource_data_source.py` | Интерфейс DataSource больше не нужен |
| `core/infrastructure/storage/file_system_data_source.py` | Парсинг YAML теперь в `ResourceLoader` |
| `core/components/services/data_repository.py` | Валидация + индекс → `ResourceLoader` |
| `core/components/services/preloading/resource_preloader.py` | Предзагрузка → `ResourceLoader.get_component_resources()` |

### Обновить `__init__.py` в пакетах

- `core/infrastructure/discovery/__init__.py` — убрать экспорт `ResourceDiscovery`
- `core/infrastructure/storage/__init__.py` — убрать экспорт `ResourceDataSource`, `FileSystemDataSource`
- `core/components/services/__init__.py` — убрать экспорт `DataRepository`, `ResourcePreloader`
- `core/infrastructure/loading/__init__.py` — **создать**, экспортировать `ResourceLoader`

---

## ✅ Этап 9: Unit-тесты на `ResourceLoader`

**Файл:** `tests/unit/infrastructure/loading/test_resource_loader.py`

### Тест-кейсы

1. **Фильтрация статусов** — `prod` игнорирует `draft`, `sandbox` принимает `draft+active`
2. **Кэширование** — повторный `get_prompt` → cache hit, без FS
3. **Fail-fast** — битый YAML → `RuntimeError` при `load_all()`
4. **component_type inference** — корректный вывод по пути
5. **direction inference** — корректный вывод по имени файла
6. **get_component_resources** — корректная выборка по `component_config`
7. **Пустые директории** — graceful handling, пустой кэш
8. **Отсутствующие обязательные поля** — `ResourceLoadError`

---

## 🚀 Этап 10: Интеграционное тестирование

1. Запустить `main.py` → логирование должно показать загрузку ресурсов за `<50мс`
2. Проверить, что компоненты получают ровно те промпты/контракты, что указаны в `ComponentConfig`
3. Проверить `profile=prod` → только `active`, `profile=sandbox` → `active+draft`
4. Замерить `time.perf_counter()` до/после `load_all()` — ожидаемое ускорение **30-50%**
5. **Проверить кэш:** `assert len(ResourceLoader._cache) == 1` (гарантия однократного скана)

---

## 🧪 Этап 11: Регрессионное тестирование

```bash
# Все тесты
python -m pytest tests/ -v

# Unit-тесты
python -m pytest tests/unit/ -v

# Integration-тесты
python -m pytest tests/integration/ -v

# С покрытием
python -m pytest tests/ --cov=core --cov-report=html
```

---

## 📋 Чек-лист миграции (пошагово)

- [ ] **Этап 1:** Создать `core/infrastructure/loading/resource_loader.py` (с `get()` кэшем)
- [ ] **Этап 2:** Обновить `InfrastructureContext.initialize()` → `ResourceLoader.get()` + `await asyncio.to_thread()`
- [ ] **Этап 3:** Обновить `ComponentFactory` → прямой вызов `get_component_resources()`
- [ ] **Этап 4:** Исправить типы в `ComponentConfig` → `Dict[str, Prompt]` / `Dict[str, Contract]`
- [ ] **Этап 5:** Обновить `ApplicationContext` → убрать `FileSystemDataSource` + `DataRepository`
- [ ] **Этап 6:** Обновить `AppConfig.from_discovery()` → использовать `ResourceLoader.get()`
- [ ] **Этап 7:** Найти и обновить все ссылки на удаляемые классы
- [ ] **Этап 7.1:** Рефакторинг `PromptService` / `ContractService` на `component_config.resolved_*`
- [ ] **Этап 8:** Удалить 5 легаси файлов + обновить `__init__.py`
- [ ] **Этап 9:** Написать unit-тесты на `ResourceLoader`
- [ ] **Этап 10:** Запустить проект → убедиться, что старт проходит без ошибок + `assert len(ResourceLoader._cache) == 1`
- [ ] **Этап 11:** Запустить все тесты + validation скрипты
- [ ] **Этап 12:** Зафиксировать метрики старта (должно стать быстрее)

---

## 💡 Почему это проще и надёжнее

| Критерий | Было | Стало |
|----------|------|-------|
| **Слоёв** | 4 (`Discovery` → `DataSource` → `Repository` → `Preloader`) | 1 (`ResourceLoader`) |
| **Проходов по ФС** | 2-3 (сканирование + загрузка по запросу) | 1 (при старте) |
| **Кэширование** | Размазано по 3 классам | Единый dict в loader |
| **Валидация** | Разделена между `Repository` и `Preloader` | Fail-fast при парсинге + silent fallback при запросе |
| **Строк кода** | ~850 | ~180 |
| **Поддержка** | Нужно менять 4 класса при смене формата YAML | Меняется только `_scan_dir()` |

---

## 🔑 Ключевые файлы

| Файл | Роль после миграции |
|------|---------------------|
| `core/infrastructure/loading/resource_loader.py` | **ЕДИНЫЙ** загрузчик ресурсов |
| `core/infrastructure_context/infrastructure_context.py` | Содержит `resource_loader` |
| `core/agent/components/component_factory.py` | Вызывает `loader.get_component_resources()` |
| `core/config/component_config.py` | `resolved_*` с корректными типами |
| `core/config/app_config.py` | `from_discovery()` через `ResourceLoader` |
| `core/application_context/application_context.py` | Без `DataRepository` и `FileSystemDataSource` |
