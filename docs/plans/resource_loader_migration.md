# План миграции на единую систему `ResourceLoader`

> **Дата:** 10 апреля 2026  
> **Статус:** ✅ ЗАВЕРШЕНА  
> **Принцип:** «Тяжёлые ресурсы — общие. Лёгкое поведение — изолированное. Конфигурация — строго иерархическая без дублирования.»

---

## 🎯 Архитектура (схема потока)

```
AppConfig(profile, data_dir)
        │
        ▼
 InfrastructureContext.initialize()
        │ → ResourceLoader.get(data_dir, profile, logger=self.log)
        │ → scan → parse → validate → cache (asyncio.to_thread)
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

## ⚠️ Критические риски (закрыты патчами)

### 🔴 Риск 1: Двойное сканирование ФС
`AppConfig.from_discovery()` и `InfrastructureContext` создают отдельные `ResourceLoader`.

**✅ Закрытие:** `ResourceLoader.get()` — фабричный метод с class-level кэшем `(data_dir, profile)`.

### 🔴 Риск 2: `PromptService` и `ContractService` ждут `DataRepository`
**✅ Закрытие:** Ресурсы уже в `component_config.resolved_*` — передаются через `ComponentFactory`.

### 🔴 Риск 3: Синхронный `load_all()` в `async`-контексте
**✅ Закрытие:** `await asyncio.to_thread(self.resource_loader.load_all)` (Python 3.9+).

---

## 📦 Этап 1: Создание `ResourceLoader` (ядро)

**Файл:** `core/infrastructure/loading/resource_loader.py` ✅ СОЗДАН

### API

```python
class ResourceLoader:
    PROFILE_STATUSES = {
        "prod": {PromptStatus.ACTIVE},
        "sandbox": {PromptStatus.ACTIVE, PromptStatus.DRAFT},
        "dev": {PromptStatus.ACTIVE, PromptStatus.DRAFT, PromptStatus.INACTIVE},
    }

    _cache: Dict[Tuple[Path, str], "ResourceLoader"] = {}

    @classmethod
    def get(cls, data_dir: Path, profile: str = "prod", logger: logging.Logger = None) -> "ResourceLoader":
        """Фабричный метод с кэшированием. Одно сканирование на (data_dir, profile)."""

    def load_all(self) -> None:
        """Однократное сканирование, парсинг и кэширование. Fail-fast при битом YAML."""

    def get_prompt(self, capability: str, version: str) -> Optional[Prompt]
    def get_contract(self, capability: str, version: str, direction: str) -> Optional[Contract]
    def get_all_prompts(self) -> List[Prompt]
    def get_all_contracts(self) -> List[Contract]
    def get_component_resources(component_name: str, config: ComponentConfig) -> Dict[str, Any]
    def get_stats(self) -> Dict[str, int]
```

### Ключевые правила

1. **Fail-fast** — битый YAML → `ResourceLoadError` при старте
2. **Фильтрация по статусу** — профиль определяет разрешённые статусы
3. **Один проход по ФС** — `load_all()` сканирует один раз
4. **Логирование** — через переданный `logger` с `extra={"event_type": LogEventType.XXX}`
5. **Инференция** — `component_type` из пути, `direction` из имени файла

---

## 🔧 Этап 2: Интеграция в `InfrastructureContext`

**Файл:** `core/infrastructure_context/infrastructure_context.py` ✅ ОБНОВЛЁН

- `ResourceDiscovery` → `ResourceLoader`
- `await asyncio.to_thread(self.resource_loader.load_all)`
- `self.log` передаётся в `ResourceLoader.get(logger=self.log)`
- Убран импорт `ResourceDiscovery`
- `self.resource_loader` вместо `self.resource_discovery`
- `get_resource_loader()` вместо `get_resource_discovery()`

---

## 🏗️ Этап 3: Обновление `ComponentFactory`

**Файл:** `core/agent/components/component_factory.py` ✅ ОБНОВЛЁН

- Удалён `_get_resource_preloader()` и `self._resource_preloader`
- Прямой вызов: `self._infrastructure_context.resource_loader.get_component_resources(name, component_config)`

---

## 📝 Этап 4: Исправление типов в `ComponentConfig`

**Файл:** `core/config/component_config.py` ✅ ОБНОВЛЁН

```python
# Было:
resolved_prompts: Dict[str, str]
resolved_input_contracts: Dict[str, Dict]
resolved_output_contracts: Dict[str, Dict]

# Стало:
resolved_prompts: Dict[str, Prompt]
resolved_input_contracts: Dict[str, Contract]
resolved_output_contracts: Dict[str, Contract]
```

---

## 🗃️ Этап 5: Обновление `ApplicationContext`

**Файл:** `core/application_context/application_context.py` ✅ ОБНОВЛЁН

- Удалены `FileSystemDataSource` + `DataRepository`
- `_auto_fill_config()` — без `discovery` параметра
- `get_prompt()` / `get_input_contract_schema()` — через `resource_loader`
- `_validate_versions_by_profile()` — через `resource_loader`
- `shutdown()` — убран `data_repository.shutdown()`

---

## 🔄 Этап 6: Обновление `AppConfig.from_discovery()`

**Файл:** `core/config/app_config.py` ✅ ОБНОВЛЁН

- `ResourceDiscovery` → `ResourceLoader.get()`
- `loader.get_all_prompts()` / `loader.get_all_contracts()` вместо `discovery.discover_*()`

---

## 🔗 Этап 7: Обновление внешних ссылок

| Файл | Изменение |
|---|---|
| `core/agent/factory.py` | `_validate_version_consistency()` → через `resource_loader` |
| `core/agent/components/optimization/version_promoter.py` | Убран `FileSystemDataSource`, прямая запись YAML |
| `core/components/skills/meta_component_creator/dynamic_loader.py` | Убран `ResourceDiscovery` |
| `core/agent/components/base_component.py` | Комментарий обновлён |
| `main.py` | Убран `discovery=` параметр |
| `diagnose_sql.py` | `ResourceDiscovery` → `ResourceLoader` |

---

### 🔧 Этап 7.1: Миграция `PromptService` / `ContractService`

Ресурсы уже в `component_config.resolved_*` — компоненты берут их напрямую.

---

## 🗑️ Этап 8: Удаление легаси

| Удалено | Причина |
|---|---|
| `core/infrastructure/discovery/` (весь пакет) | Сканирование → `ResourceLoader` |
| `core/infrastructure/storage/resource_data_source.py` | Интерфейс не нужен |
| `core/infrastructure/storage/file_system_data_source.py` | Загрузка → `ResourceLoader` |
| `core/infrastructure/storage/mock_database_resource_data_source.py` | Ссылался на удалённый интерфейс |
| `core/components/services/data_repository.py` | Валидация → `ResourceLoader` |
| `core/components/services/preloading/` (весь пакет) | Предзагрузка → `ResourceLoader` |

---

## ✅ Этап 9: Unit-тесты

**Файл:** `tests/unit/infrastructure/loading/test_resource_loader.py` ✅ СОЗДАН

- 20 тестов, все passed
- Покрытие: базовая загрузка, фильтрация по профилю, кэширование, `get_component_resources`, инференция, fail-fast

---

## 🚀 Этап 10: Интеграционное тестирование

- ✅ `main.py` запускается без ошибок
- ✅ Все 18+ компонентов создаются и регистрируются
- ✅ Агент начинает работу (`Pattern.decide()`)
- ✅ Логи в `infra_context.log` показывают все этапы включая ЭТАП 3.5

---

## 💡 Архитектурные улучшения (дополнительные фиксы)

| Файл | Проблема | Решение |
|---|---|---|
| `SkillHandler.__init__` | Legacy-код вызывал `SkillHandler(skill)` без аргументов | Обратная совместимость: извлечение из `skill` |
| `SkillHandler._execute_impl` | Абстрактный метод — legacy-хендлеры не реализовали | Дефолтная реализация → делегирование в `execute()` |
| `book_library/skill.py` | Хендлеры создавались без нужных аргументов | Передача `component_config`, `executor`, `event_bus` |
| SQLite | Не использовался, вызывал ошибки при старте | Удалён из конфигов, типов, фабрики |
| `_validate_versions_by_profile` | Использовал удалённый `data_repository` | Переведён на `resource_loader` |

---

## 📊 Итоговые метрики

| Критерий | Было | Стало |
|----------|------|-------|
| **Слоёв** | 4 (`Discovery` → `DataSource` → `Repository` → `Preloader`) | 1 (`ResourceLoader`) |
| **Проходов по ФС** | 2-3 | 1 |
| **Кэширование** | Размазано по 3 классам | Единый dict в loader |
| **Строк кода** | ~850 | ~180 |

---

## 📋 Чек-лист (итоговый)

- [x] **Этап 1:** `core/infrastructure/loading/resource_loader.py` с `get()` кэшем и `logger`
- [x] **Этап 2:** `InfrastructureContext.initialize()` → `ResourceLoader.get()` + `asyncio.to_thread()`
- [x] **Этап 3:** `ComponentFactory` → прямой вызов `get_component_resources()`
- [x] **Этап 4:** Типы `ComponentConfig` → `Dict[str, Prompt]` / `Dict[str, Contract]`
- [x] **Этап 5:** `ApplicationContext` → убраны `FileSystemDataSource` + `DataRepository`
- [x] **Этап 6:** `AppConfig.from_discovery()` → `ResourceLoader.get()`
- [x] **Этап 7:** Все ссылки на удалённые классы обновлены
- [x] **Этап 7.1:** `PromptService` / `ContractService` → `component_config.resolved_*`
- [x] **Этап 8:** Удалено 5+ файлов, обновлены `__init__.py`
- [x] **Этап 9:** 20 unit-тестов passed
- [x] **Этап 10:** `main.py` запускается, все компоненты инициализированы
- [x] **Этап 11:** Логи корректны, `LogEventType` используется
- [x] **Этап 12:** SQLite удалён, legacy-баги исправлены
