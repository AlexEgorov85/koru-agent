# Отчёт о миграции на интерфейсы

## Статус: В ПРОЦЕССЕ

**Дата:** 2026-03-06  
**Цель:** Убрать прямые зависимости компонентов от контекстов, использовать только интерфейсы

---

## ✅ Выполнено

### 1. Базовые интерфейсы (созданы)
- `core/interfaces/database.py` - DatabaseInterface
- `core/interfaces/llm.py` - LLMInterface
- `core/interfaces/vector.py` - VectorInterface
- `core/interfaces/cache.py` - CacheInterface
- `core/interfaces/prompt_storage.py` - PromptStorageInterface
- `core/interfaces/contract_storage.py` - ContractStorageInterface
- `core/interfaces/event_bus.py` - EventBusInterface
- `core/interfaces/metrics_storage.py` - MetricsStorageInterface
- `core/interfaces/log_storage.py` - LogStorageInterface

### 2. Провайдеры реализуют интерфейсы (обновлены)
- `core/infrastructure/providers/database/postgres_provider.py` → PostgreSQLProvider implements DatabaseInterface
- `core/infrastructure/providers/llm/llama_cpp_provider.py` → LlamaCppProvider implements LLMInterface
- `core/infrastructure/providers/vector/faiss_provider.py` → FAISSProvider implements VectorInterface
- `core/infrastructure/providers/cache/memory_cache_provider.py` → MemoryCacheProvider implements CacheInterface (НОВЫЙ)

### 3. BaseComponent обновлён
**Файл:** `core/components/base_component.py`

**Изменения:**
- Добавлены параметры конструктора для внедрения зависимостей:
  ```python
  def __init__(
      self,
      name: str,
      application_context: Optional['ApplicationContext'] = None,  # DEPRECATED
      component_config: Optional[ComponentConfig] = None,
      executor: Optional['ActionExecutor'] = None,
      # === ВНЕДРЕНИЕ ЗАВИСИМОСТЕЙ ЧЕРЕЗ ИНТЕРФЕЙСЫ ===
      db: Optional[DatabaseInterface] = None,
      llm: Optional[LLMInterface] = None,
      cache: Optional[CacheInterface] = None,
      vector: Optional[VectorInterface] = None,
      event_bus: Optional[EventBusInterface] = None,
      prompt_storage: Optional[PromptStorageInterface] = None,
      contract_storage: Optional[ContractStorageInterface] = None,
      metrics_storage: Optional[MetricsStorageInterface] = None,
      log_storage: Optional[LogStorageInterface] = None
  ):
  ```

- Добавлены свойства для доступа к внедрённым зависимостям:
  ```python
  @property
  def db(self) -> Optional[DatabaseInterface]: ...
  
  @property
  def llm(self) -> Optional[LLMInterface]: ...
  
  @property
  def cache(self) -> Optional[CacheInterface]: ...
  ```

- `application_context` помечен как DEPRECATED с предупреждением

### 4. ComponentFactory обновлён
**Файл:** `core/application/components/component_factory.py`

**Изменения:**
- Конструктор принимает InfrastructureContext:
  ```python
  def __init__(self, infrastructure_context: InfrastructureContext):
  ```

- Метод `_get_providers()` получает провайдеры из инфраструктурного контекста
- `create_and_initialize()` передаёт провайдеры как интерфейсы в компоненты

---

## ⚠️ Требуют обновления

### Сервисы (3 файла)

| Файл | Проблема | Что изменить |
|------|----------|--------------|
| `core/application/services/prompt_service.py` | `self.application_context.infrastructure_context.get_prompt_storage()` | Добавить параметр `prompt_storage: PromptStorageInterface` |
| `core/application/services/contract_service.py` | `self.application_context.infrastructure_context.get_contract_storage()` | Добавить параметр `contract_storage: ContractStorageInterface` |
| `core/application/services/base_service.py` | `self.application_context.infrastructure_context.event_bus` | Добавить параметр `event_bus: EventBusInterface` |

### Навыки (4 файла)

| Файл | Проблема | Что изменить |
|------|----------|--------------|
| `core/application/skills/book_library/skill.py` | `self.application_context.infrastructure_context.event_bus` | Использовать `self.event_bus` из BaseComponent |
| `core/application/skills/planning/skill.py` | `self.application_context.infrastructure_context.event_bus` | Использовать `self.event_bus` |
| `core/application/skills/data_analysis/skill.py` | `self.application_context.components.get(...)` | Внедрить зависимости через конструктор |
| `core/application/skills/final_answer/skill.py` | `self.application_context.infrastructure_context.event_bus` | Использовать `self.event_bus` |

### Инструменты (3 файла)

| Файл | Проблема | Что изменить |
|------|----------|--------------|
| `core/application/tools/sql_tool.py` | `self.application_context.infrastructure_context.event_bus` | Использовать `self.event_bus` |
| `core/application/tools/file_tool.py` | `self.application_context.infrastructure_context.config` | Внедрить конфигурацию или использовать DI |
| `core/application/tools/vector_books_tool.py` | `self.application_context.infrastructure_context` | Использовать внедрённые зависимости |

### Behavior Patterns (3 файла)

| Файл | Проблема | Что изменить |
|------|----------|--------------|
| `core/application/behaviors/react/pattern.py` | `self.application_context.llm_orchestrator`, `get_provider()` | Добавить параметр `llm: LLMInterface` |
| `core/application/behaviors/evaluation/pattern.py` | `self.application_context.llm_orchestrator` | Добавить параметр `llm: LLMInterface` |
| `core/application/behaviors/planning/pattern.py` | `self.application_context` | Использовать внедрённые зависимости |

### Другие компоненты (4 файла)

| Файл | Проблема | Что изменить |
|------|----------|--------------|
| `core/application/agent/components/action_executor.py` | `self.application_context.get_provider()`, `llm_orchestrator` | Внедрить LLMInterface напрямую |
| `core/application/agent/runtime.py` | Множественные обращения к `application_context` | Рефакторинг на использование интерфейсов |
| `core/application/agent/factory.py` | `self.application_context.infrastructure_context` | Использовать InfrastructureContext напрямую |
| `core/application/storage/behavior/behavior_storage.py` | `self._application_context.config` | Внедрить конфигурацию |

---

## 🔍 Анализ: где используются интерфейсы, а где нет

### ✅ Уже используют интерфейсы (через BaseComponent)

Компоненты которые **не имеют прямых обращений** к `application_context.infrastructure_context`:

1. **Новые сервисы** (после обновления):
   - PromptService (частично)
   - ContractService (частично)

2. **BaseComponent** - предоставляет свойства для всех интерфейсов

### ❌ Прямые обращения к контекстам (77 мест)

**Категории проблем:**

1. **Доступ к провайдерам через `get_provider()`** (15 мест):
   ```python
   # ❌ ПЛОХО
   db = self.application_context.infrastructure_context.get_provider("default_db")
   
   # ✅ ХОРОШО
   db = self.db  # или через параметр конструктора
   ```

2. **Доступ к хранилищам напрямую** (8 мест):
   ```python
   # ❌ ПЛОХО
   storage = self.application_context.infrastructure_context.get_prompt_storage()
   
   # ✅ ХОРОШО
   storage = self.prompt_storage  # или через параметр конструктора
   ```

3. **Доступ к шине событий** (20 мест):
   ```python
   # ❌ ПЛОХО
   event_bus = self.application_context.infrastructure_context.event_bus
   
   # ✅ ХОРОШО
   event_bus = self.event_bus  # или через параметр конструктора
   ```

4. **Доступ к registry компонентов** (15 мест):
   ```python
   # ❌ ПЛОХО
   tool = self.application_context.components.get(ComponentType.TOOL, "sql_tool")
   
   # ✅ ХОРОШО
   # Внедрить через конструктор или использовать ActionExecutor
   result = await self.executor.execute_action("sql_tool.execute", ...)
   ```

5. **Доступ к конфигурации** (10 мест):
   ```python
   # ❌ ПЛОХО
   config = self.application_context.config
   
   # ✅ ХОРОШО
   # Использовать component_config или внедрить AppConfig
   ```

6. **Доступ к llm_orchestrator** (5 мест):
   ```python
   # ❌ ПЛОХО
   llm = self.application_context.llm_orchestrator
   
   # ✅ ХОРОШО
   llm = self.llm  # LLMInterface
   ```

7. **Доступ к session_context** (10 мест):
   ```python
   # ❌ ПЛОХО
   ctx = self.application_context.session_context
   
   # ✅ ХОРОШО
   # session_context - это часть ApplicationContext, требует отдельного решения
   ```

---

## 📋 План завершения миграции

### Этап 1: Обновить сервисы (приоритет высокий)

1. **BaseService** - добавить параметры для интерфейсов
2. **PromptService** - использовать `prompt_storage` из BaseComponent
3. **ContractService** - использовать `contract_storage` из BaseComponent

### Этап 2: Обновить навыки

1. **BookLibrarySkill** - уже использует `self.application_context`, обновить на DI
2. **PlanningSkill** - убрать доступ к infrastructure_context
3. **DataAnalysisSkill** - внедрить зависимости через конструктор
4. **FinalAnswerSkill** - использовать внедрённые зависимости

### Этап 3: Обновить инструменты

1. **SQLTool** - использовать внедрённый db
2. **FileTool** - использовать внедрённую конфигурацию
3. **VectorBooksTool** - использовать внедрённый vector

### Этап 4: Обновить behavior patterns

1. **ReActPattern** - внедрить LLMInterface
2. **EvaluationPattern** - внедрить LLMInterface
3. **PlanningPattern** - использовать внедрённые зависимости

### Этап 5: Обновить agent runtime

1. **ActionExecutor** - внедрить LLMInterface
2. **Runtime** - рефакторинг на использование интерфейсов
3. **AgentFactory** - использовать InfrastructureContext напрямую

---

## 🎯 Критерии завершения

- [ ] Ни один компонент не использует `self.application_context.infrastructure_context`
- [ ] Все провайдеры передаются через конструкторы компонентов
- [ ] Все тесты обновлены на использование mock-интерфейсов
- [ ] Удалены все методы `get_provider()`, `get_service()` из контекстов
- [ ] Документация обновлена

---

## 📊 Статистика

| Категория | Файлов | Готово | Осталось |
|-----------|--------|--------|----------|
| Интерфейсы | 9 | 9 (100%) | 0 |
| Провайдеры | 4 | 4 (100%) | 0 |
| BaseComponent | 1 | 1 (100%) | 0 |
| ComponentFactory | 1 | 1 (100%) | 0 |
| Сервисы | 7 | 0 (0%) | 7 |
| Навыки | 4 | 0 (0%) | 4 |
| Инструменты | 3 | 0 (0%) | 3 |
| Behavior Patterns | 4 | 0 (0%) | 4 |
| Agent Runtime | 3 | 0 (0%) | 3 |
| **ВСЕГО** | **36** | **15 (42%)** | **21 (58%)** |

---

*Отчёт создан: 2026-03-06*
