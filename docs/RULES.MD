# Требования к Разработке Агента — Agent v5

> **Версия:** 5.36.0
> **Статус:** Active
> **Дата обновления:** 2026-03-15
> **Владелец:** @system
> **Последние изменения:**
> - v5.36.0: Добавлены рекомендации по промптам и контрактам, исправлены ошибки в final_answer
> - v5.4.0: Обновлена архитектура загрузки промптов и контрактов (ResourcePreloader)
> - v5.3.0: Исправлены ошибки в документации, добавлены новые секции
> - v5.2.0: Введён `ComponentLogger` — логирование через стандартный `logging` с `LogEventType`

---

## 📋 Содержание

1. [Принципы Архитектуры](#принципы-архитектуры)
2. [Существующие Абстракции](#существующие-абстракции)
3. [Требования к Компонентам](#требования-к-компонентам)
4. [Требования к Взаимодействию](#требования-к-взаимодействию)
5. [Требования к Логированию и Метрикам](#требования-к-логированию-и-метрикам)
6. [Требования к Валидации](#требования-к-валидации)
7. [Запрещённые Паттерны](#запрещённые-паттерны)
8. [Обоснование Новых Абстракций](#обоснование-новых-абстракций)
9. [Чеклист Перед Коммитом](#чеклист-перед-коммитом)

---

## 🏗️ Принципы Архитектуры

### 1. Не Изобретай Велосипед

| Принцип | Описание | Пример |
|---------|----------|--------|
| **Используй BaseComponent** | Все навыки, инструменты, сервисы наследуются от `BaseComponent` | `class MySkill(BaseSkill)` |
| **Используй ActionExecutor** | Взаимодействие между компонентами ТОЛЬКО через executor | `await self.executor.execute_action(...)` |
| **Используй стандартный logging** | Логирование через `self.log` + `extra={"event_type": LogEventType.XXX}` | `self.log.info("Message", extra={"event_type": LogEventType.INFO})` |
| **Используй ComponentConfig** | Конфигурация версий через `component_config` | `self.component_config.prompt_versions` |

### 2. Изоляция Компонентов

```
┌─────────────────────────────────────────────────────────────┐
│                    ApplicationContext                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Skill A   │  │   Skill B   │  │   Tool C    │          │
│  │  (isolated) │  │  (isolated) │  │  (isolated) │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                  │
│         └────────────────┼────────────────┘                  │
│                          ▼                                   │
│               ┌──────────────────┐                           │
│               │  ActionExecutor  │ ← ЕДИНАЯ точка доступа    │
│               └──────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

**Правило:** Компоненты НЕ знают друг о друге. Все взаимодействия через `ActionExecutor`.

### 3. Жизненный Цикл

```
CREATED → INITIALIZING → READY → SHUTDOWN
                ↓
              FAILED (при ошибке)
```

**Требования:**
- ✅ Вызови `await super().initialize()` в начале инициализации
- ✅ Проверяй состояние через `self._state` или `self.is_ready`
- ✅ Реализуй `shutdown()` для очистки ресурсов

### 4. Архитектурные Гарантии

**Гарантия 1: Никакого общего состояния между агентами**
```python
# ✅ ПРАВИЛЬНО: Изолированный кэш на агента
class PromptService(BaseService):
    def __init__(self, application_context: ApplicationContext):
        self._isolated_cache = {}  ← Изолированный кэш

# ❌ ЗАПРЕЩЕНО: Общий кэш = утечка состояния
class PromptService(BaseService):
    _shared_cache = {}  ← Ошибка архитектуры
```

**Гарантия 2: Инфраструктура — только для чтения**
```python
# ✅ ПРАВИЛЬНО: Только чтение из инфраструктуры
prompt = app_ctx.infrastructure.prompt_storage.load(cap, ver)

# ❌ ЗАПРЕЩЕНО: Изменение инфраструктуры
app_ctx.infrastructure.register_resource("x", y)  ← Ошибка
```

**Гарантия 3: Профиль определяет разрешённые статусы**
| Профиль | Разрешённые статусы | Поведение |
|---------|---------------------|-----------|
| `prod` | Только `active` | Исключение при нарушении |
| `sandbox` | `draft` + `active` | Предупреждение для `draft` |
| `dev` | Все статусы | Без ограничений |

**Гарантия 4: Однократная загрузка ресурсов**
```python
# При инициализации:
await data_repository.initialize(app_config)  ← 1 раз, загрузка в индексы

# Во время выполнения:
prompt = data_repository.get_prompt(cap, ver)  ← Из кэша, 0 обращений к ФС
```

### 5. Архитектура Загрузки Ресурсов и Конфигурация

**Принципы:**

| Принцип | Описание |
|---------|----------|
| **Компоненты не знают о версиях** | Версии определяются в `AppConfig` через `from_discovery(profile)` |
| **Профиль управляет загрузкой** | `prod` = active, `sandbox` = active + draft, `dev` = все статусы |
| **Единая точка загрузки** | `ResourceLoader` загружает всё один раз при старте |
| **ComponentFactory заполняет resolved_*** | Factory вызывает `ResourceLoader.get_component_resources()` |
| **Компонент получает готовые ресурсы** | `self.prompts`, `self.input_contracts` уже загружены |

**Иерархия конфигурации:**

```
SystemConfig (InfraConfig)     ← core/config/defaults/{profile}.yaml
    ↓                              Тяжёлые ресурсы: llm_providers, db_providers
AppConfig                      ← data/ + from_discovery(profile)
    ↓                              Поведение: prompt_versions, contract_versions
ComponentConfig                ← Генерируется из AppConfig
    ↓                              Ресурсы компонента: resolved_prompts, resolved_contracts
Компонент (Skill/Tool/Service) ← Использует готовые ресурсы
```

**Поток загрузки:**

```
┌──────────────────────────────────────────────────────────────┐
│  AppConfig.from_discovery(profile='prod')                    │
│  → Загружает llm_providers, db_providers из YAML            │
│  → ResourceLoader сканирует ФС, фильтрует по статусу         │
│  → Возвращает {prompt_versions, input_contract_versions...} │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  ComponentFactory.create_component()                         │
│  → Берёт component_config из AppConfig                       │
│  → Вызывает ResourceLoader.get_component_resources()         │
│  → Заполняет component_config.resolved_*                     │
│  → Создаёт компонент с готовыми ресурсами                    │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Component (BookLibrarySkill, PlanningSkill, etc.)           │
│  → НЕ загружает ничего сам                                   │
│  → Использует self.prompts, self.input_contracts...          │
│  → Только валидирует что ресурсы загружены                   │
└──────────────────────────────────────────────────────────────┘
```

**Требования к компонентам:**

```python
# ✅ ПРАВИЛЬНО: Компонент НЕ загружает ресурсы сам
class MySkill(BaseSkill):
    async def initialize(self) -> bool:
        # Вызови родительский initialize()
        success = await super().initialize()
        if not success:
            return False
        
        # Ресурсы УЖЕ загружены в component_config.resolved_*
        # Только проверь что они есть (если требуются)
        if self._requires_prompts() and not self.prompts:
            raise ComponentInitializationError("Промпты не загружены")
        
        return True

# ❌ НЕПРАВИЛЬНО: Компонент загружает ресурсы сам
async def _load_prompts(self):  # ← Удалить!
    for cap, ver in self.component_config.prompt_versions.items():
        prompt = await self.application_context.get_prompt(cap, ver)
        self.prompts[cap] = prompt
```

**Требования к ComponentFactory:**

```python
# ✅ ПРАВИЛЬНО: Factory загружает ресурсы перед созданием
class ComponentFactory:
    async def create_and_initialize(
        self,
        component_class: Type[BaseComponent],
        name: str,
        component_config: ComponentConfig
    ) -> BaseComponent:
        # 1. Загружаем ресурсы ДО создания компонента
        resources = await self.preloader.preload_for_component(
            name, component_config
        )
        
        # 2. Заполняем component_config.resolved_*
        component_config.resolved_prompts = resources["prompts"]
        component_config.resolved_input_contracts = resources["input_contracts"]
        component_config.resolved_output_contracts = resources["output_contracts"]
        
        # 3. Создаём компонент с готовыми ресурсами
        component = component_class(
            name=name,
            component_config=component_config,  # ← С ресурсами!
            ...
        )
        
        await component.initialize()
        return component
```

---

## 📦 Существующие Абстракции

### Базовые Классы

| Класс | Файл | Назначение | Когда Использовать |
|-------|------|------------|-------------------|
| `BaseComponent` | `core/components/base_component.py` | Базовый класс для всех компонентов | Всегда для навыков/инструментов/сервисов |
| `BaseSkill` | `core/application/skills/base_skill.py` | Базовый класс для навыков | Для навыков (логика принятия решений) |
| `BaseTool` | `core/application/tools/base_tool.py` | Базовый класс для инструментов | Для инструментов (выполнение действий) |
| `BaseService` | `core/application/services/base_service.py` | Базовый класс для сервисов | Для сервисов (инфраструктурная логика) |
| `BaseBehaviorPattern` | `core/application/behaviors/base_behavior_pattern.py` | Базовый класс для паттернов | Для паттернов поведения (ReAct, Planning) |

### Конфигурация

| Класс | Файл | Назначение |
|-------|------|------------|
| `ComponentConfig` | `core/config/component_config.py` | Конфигурация компонента с версиями ресурсов |
| `AppConfig` | `core/config/app_config.py` | Единая конфигурация приложения |
| `AgentConfig` | `core/config/agent_config.py` | Конфигурация агента для сессии |

### Контексты

| Класс | Файл | Назначение |
|-------|------|------------|
| `ExecutionContext` | `core/application/agent/components/action_executor.py` | Контекст выполнения действия |
| `SessionContext` | `core/session_context/session_context.py` | Контекст сессии агента |
| `ApplicationContext` | `core/application/context/application_context.py` | Прикладной контекст |
| `InfrastructureContext` | `core/infrastructure/context/infrastructure_context.py` | Инфраструктурный контекст |

### Взаимодействие

| Класс | Файл | Назначение |
|-------|------|------------|
| `ActionExecutor` | `core/application/agent/components/action_executor.py` | **ЕДИНСТВЕННЫЙ** способ взаимодействия между компонентами |
| `LLMOrchestrator` | `core/infrastructure/providers/llm/llm_orchestrator.py` | Централизованное управление LLM вызовами |
| `EventBus` | `core/infrastructure/event_bus/unified_event_bus.py` | Шина событий для логирования и метрик |

### Ресурсы

| Класс | Файл | Назначение |
|-------|------|------------|
| `ResourceLoader` | `core/infrastructure/loading/resource_loader.py` | ЕДИНЫЙ загрузчик промптов и контрактов |
| `ComponentRegistry` | `core/agent/components/component_registry.py` | Реестр компонентов |

### Модели Данных

| Класс | Файл | Назначение |
|-------|------|------------|
| `ExecutionResult` | `core/models/data/execution.py` | **ЕДИНЫЙ** формат результата выполнения |
| `Capability` | `core/models/data/capability.py` | Декларация возможности компонента |
| `Prompt` | `core/models/data/prompt.py` | Типизированный объект промпта |
| `Contract` | `core/models/data/contract.py` | Типизированный объект контракта с Pydantic схемой |

---

## ⚙️ Требования к Компонентам

### 1. Структура Компонента

```python
from core.application.skills.base_skill import BaseSkill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from typing import List, Dict, Any

class MySkill(BaseSkill):
    """
    Описание навыка.
    
    CAPABILITIES:
    - my_skill.do_something - описание capability
    """
    
    # Явная декларация зависимостей
    DEPENDENCIES = ["sql_tool", "prompt_service"]
    
    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="my_skill.do_something",
                description="Описание capability",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0",
                    "requires_llm": True
                }
            )
        ]
    
    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],  # ← Уже валидированы через Pydantic!
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:  # ← Возвращаем данные, НЕ ExecutionResult!
        # Твоя бизнес-логика здесь
        return {"result": "done"}
```

### 2. Инициализация

```python
async def initialize(self) -> bool:
    # 1. Вызови родительский initialize()
    success = await super().initialize()
    if not success:
        return False

    # 2. Загрузи дополнительные ресурсы (если нужно)
    # self.prompts и self.input_contracts уже загружены!

    # 3. Логирование
    self.log.info(f"{self.name} инициализирован", extra={"event_type": LogEventType.SYSTEM_INIT})

    return True
```

### 3. Выполнение

```python
async def _execute_impl(self, capability, parameters, execution_context):
    # ✅ ПРАВИЛЬНО: parameters уже валидированы через Pydantic
    query = parameters.query  # IDE автокомплит работает!
    max_results = parameters.max_results
    
    # ✅ ПРАВИЛЬНО: Взаимодействие через executor
    result = await self.executor.execute_action(
        action_name="sql_tool.execute",
        parameters={"query": query},
        context=execution_context
    )
    
    # ✅ ПРАВИЛЬНО: Возвращаем данные (не ExecutionResult!)
    return {"rows": result.data.get("rows", [])}
```

### 4. Валидация Входных/Выходных Данных

**НЕ ДЕЛАЙ:**
```python
# ❌ НЕ ПРАВИЛЬНО: Ручная валидация
if "query" not in parameters:
    raise ValueError("query required")
```

**ДЕЛАЙ:**
```python
# ✅ ПРАВИЛЬНО: Валидация через контракты (автоматически в BaseComponent.execute())
# Контракты определяются в YAML файлах data/contracts/
# parameters уже валидированная Pydantic модель!
```

**Структура контракта (YAML):**
```yaml
# data/contracts/skill/my_skill/my_skill.do_something_input_v1.0.0.yaml
capability: my_skill.do_something
version: v1.0.0
status: active
component_type: skill
direction: input
schema_data:
  type: object
  properties:
    query:
      type: string
      description: Поисковый запрос
    max_results:
      type: integer
      description: Максимальное количество результатов
      default: 10
  required:
    - query
```

---

## 🔗 Требования к Взаимодействию

### 1. Вызов Других Компонентов

**НЕ ДЕЛАЙ:**
```python
# ❌ ЗАПРЕЩЕНО: Прямой доступ к компонентам
other_skill = self.application_context.components.get(ComponentType.SKILL, "other_skill")
result = await other_skill.execute(...)

# ❌ ЗАПРЕЩЕНО: Прямой доступ к инфраструктуре
db = self.application_context.infrastructure_context.get_provider("default_db")
```

**ДЕЛАЙ:**
```python
# ✅ ПРАВИЛЬНО: Через ActionExecutor
result = await self.executor.execute_action(
    action_name="other_skill.do_something",
    parameters={"param": "value"},
    context=execution_context
)

# ✅ ПРАВИЛЬНО: Через executor для инфраструктуры
result = await self.executor.execute_action(
    action_name="sql_tool.execute",
    parameters={"query": "SELECT ..."},
    context=execution_context
)
```

### 2. Вызов LLM

**НЕ ДЕЛАЙ:**
```python
# ❌ ЗАПРЕЩЕНО: Прямой вызов LLM провайдера
llm = self.application_context.infrastructure_context.get_provider("default_llm")
response = await llm.generate(prompt)
```

**ДЕЛАЙ:**
```python
# ✅ ПРАВИЛЬНО: Через LLMOrchestrator (автоматически через executor)
result = await self.executor.execute_action(
    action_name="llm.generate_structured",
    parameters={
        "prompt": prompt_text,
        "structured_output": {
            "output_model": "MyOutputModel",
            "schema_def": output_schema.model_json_schema(),
            "max_retries": 3
        }
    },
    context=execution_context
)
```

### 3. Работа с Контекстом Сессии

**НЕ ДЕЛАЙ:**
```python
# ❌ ЗАПРЕЩЕНО: Прямая модификация контекста
execution_context.session_context.history.append(...)
```

**ДЕЛАЙ:**
```python
# ✅ ПРАВИЛЬНО: Через executor actions
await self.executor.execute_action(
    action_name="context.record_action",
    parameters={"action_data": {...}},
    context=execution_context
)

await self.executor.execute_action(
    action_name="context.record_observation",
    parameters={"observation_data": {...}},
    context=execution_context
)
```

---

## 📊 Требования к Логированию и Метрикам

### 1. Логирование

**АРХИТЕКТУРА:**
- Все компоненты наследуют `ComponentLogger` через `Component`
- Логгер (`self.log`) — экземпляр стандартного `logging.Logger`, получаемый из `LoggingSession.get_component_logger()`
- Источник: `application_context.infrastructure_context.log_session` → `get_component_logger(component_id)`
- Все логи пишутся в `components.log` + выводятся в консоль через `EventTypeFilter`
- **Каждый вызов ОБЯЗАН** иметь `extra={"event_type": LogEventType.XXX}` — записи без `event_type` НЕ попадают в терминал

**НЕ ДЕЛАЙ:**
```python
# ❌ ЗАПРЕЩЕНО: EventBusLogger (удалён)
await self.event_bus_logger.info("Message")

# ❌ ЗАПРЕЩЕНО: Print
print("Debug message")

# ❌ ЗАПРЕЩЕНО: Прямой logging.getLogger() без LoggingSession
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
```

**ДЕЛАЙ:**
```python
from core.infrastructure.logging.event_types import LogEventType

# ✅ ПРАВИЛЬНО: self.log + LogEventType
self.log.info("Сообщение", extra={"event_type": LogEventType.INFO})
self.log.debug("Отладка", extra={"event_type": LogEventType.DEBUG})
self.log.warning("Предупреждение", extra={"event_type": LogEventType.WARNING})
self.log.error("Ошибка", extra={"event_type": LogEventType.ERROR}, exc_info=True)

# ✅ ПРАВИЛЬНО: С контекстом выполнения
self.log.info("Начало обработки", extra={"event_type": LogEventType.STEP_STARTED})
self.log.info("Обработка завершена", extra={"event_type": LogEventType.STEP_COMPLETED})
```

**Доступные типы событий (`LogEventType`):**

| Категория | Типы |
|-----------|------|
| Пользователь | `USER_PROGRESS`, `USER_RESULT`, `USER_MESSAGE`, `USER_QUESTION` |
| Агент | `AGENT_START`, `AGENT_STOP`, `AGENT_THINKING`, `AGENT_DECISION` |
| План | `PLAN_CREATED`, `PLAN_UPDATED` |
| Шаг | `STEP_STARTED`, `STEP_COMPLETED` |
| Инструмент | `TOOL_CALL`, `TOOL_RESULT`, `TOOL_ERROR` |
| LLM | `LLM_CALL`, `LLM_RESPONSE`, `LLM_ERROR` |
| БД | `DB_QUERY`, `DB_RESULT`, `DB_ERROR` |
| Система | `SYSTEM_INIT`, `SYSTEM_READY`, `SYSTEM_SHUTDOWN`, `SYSTEM_ERROR` |
| Общие | `INFO`, `DEBUG`, `WARNING`, `ERROR`, `CRITICAL` |

**Структура файлов логов:**
```
logs/
└── 2026-04-10_14-30-00/
    ├── infra_context.log          # Инфраструктура (провайдеры, БД, LLM)
    ├── app_context.log            # Приложение (компоненты, сервисы)
    └── agents/
        └── 2026-04-10_14-31-12.log  # Сессия агента
```

### 2. Метрики

**Автоматически Публикуются:**
- Время выполнения компонента
- Успешность выполнения
- Количество токенов (для LLM вызовов)

**Дополнительные Метрики:**
```python
await self.executor.execute_action(
    action_name="metrics.record",
    parameters={
        "metric_name": "custom_metric",
        "value": 42.0,
        "tags": {"key": "value"}
    },
    context=execution_context
)
```

---

## ✅ Требования к Валидации

### 1. Входные Данные

**Автоматическая Валидация:**
- `BaseComponent.execute()` автоматически валидирует входные данные через `validate_input_typed()`
- Возвращает Pydantic модель (не dict!)
- При ошибке возвращает `ExecutionResult.failure()`

**Требования к Контрактам:**
- ✅ Все capability должны иметь input и output контракты
- ✅ Контракты хранятся в `data/contracts/{type}/{component}/`
- ✅ Версии контрактов указываются в `ComponentConfig`

### 2. Выходные Данные

**Автоматическая Валидация:**
- `BaseComponent.execute()` автоматически валидирует выходные данные через `validate_output_typed()`
- Сохраняет Pydantic модель в `ExecutionResult.data`
- Сериализация происходит только на границах (EventBus/Storage)

### 3. Промпты

**Требования:**
- ✅ Все промпты хранятся в `data/prompts/{type}/{component}/`
- ✅ Используй `self.get_prompt(capability_name)` для получения
- ✅ Используй `self.get_prompt_with_contract(capability_name)` для промпта со схемой
- ✅ Поддерживается разделение system/user промптов (автоматически при инициализации)

---

## 🚫 Запрещённые Паттерны

### 1. Прямой Доступ к Компонентам

| Нарушение | Файл для Проверки | Исправление |
|-----------|-------------------|-------------|
| `application_context.components.get` | `scripts/validation/check_skill_architecture.py` | Используй `executor.execute_action()` |
| `infrastructure_context.get_provider` | `scripts/validation/check_skill_architecture.py` | Используй `executor.execute_action()` |
| `import ComponentType` для доступа | `scripts/validation/check_skill_architecture.py` | Не импортируй для доступа |

### 2. Возврат ExecutionResult из `_execute_impl`

| Нарушение | Как Проверить | Исправление |
|-----------|---------------|-------------|
| `return ExecutionResult.success(...)` в `_execute_impl` | AST-анализ в `check_skill_architecture.py` | Возвращай данные: `return {"result": "value"}` |

### 3. Прямые Вызовы LLM API

| Нарушение | Паттерн | Исправление |
|-----------|---------|-------------|
| `openai.ChatCompletion` | `scripts/validation/check_skill_architecture.py` | Через `executor.execute_action("llm.generate")` |
| `llm_client.generate` | `scripts/validation/check_skill_architecture.py` | Через `executor.execute_action("llm.generate")` |

### 4. Retry Логика в Навыках

| Нарушение | Паттерн | Исправление |
|-----------|---------|-------------|
| `for attempt in range(3)` | `scripts/validation/check_skill_architecture.py` | Через `LLMOrchestrator` (автоматически) |
| `while retry` | `scripts/validation/check_skill_architecture.py` | Через `AgentPolicy` |

### 5. Random Usage

| Нарушение | Паттерн | Исправление |
|-----------|---------|-------------|
| `import random` | `scripts/validation/check_skill_architecture.py` | Только если обосновано (не для бизнес-логики) |
| `random.choice` | `scripts/validation/check_skill_architecture.py` | Только если обосновано |

---

## 🆕 Обоснование Новых Абстракций

### Когда Можно Создать Новую Абстракцию

| Ситуация | Требуется Обоснование | Пример |
|----------|----------------------|--------|
| Новый тип компонента | ✅ Почему не подходит Skill/Tool/Service | Новый тип с уникальным жизненным циклом |
| Новый способ взаимодействия | ✅ Почему не подходит ActionExecutor | Требует гарантированного порядка выполнения |
| Новое хранилище | ✅ Почему не подходит FileSystemStorage | Требуется распределённое хранение |
| Новый интерфейс | ✅ Почему не подходит существующий | Требует других методов/параметров |

### Шаблон Обоснования

```markdown
## Предложение Новой Абстракции: {Название}

### Проблема
{Описание проблемы, которую не решают существующие абстракции}

### Почему Существующие Не Подходят
| Абстракция | Почему Не Подходит |
|------------|-------------------|
| ActionExecutor | {Причина} |
| BaseComponent | {Причина} |
| EventBus | {Причина} |

### Предлагаемое Решение
{Описание новой абстракции}

### Влияние на Архитектуру
{Как новая абстракция интегрируется в существующую архитектуру}

### Альтернативы
{Рассмотренные альтернативы и почему они не подходят}
```

---

## 📝 Чеклист Перед Коммитом

### Код

- [ ] Наследуется от `BaseComponent` (или `BaseSkill`/`BaseTool`/`BaseService`)
- [ ] Взаимодействие через `ActionExecutor` (нет прямого доступа к компонентам)
- [ ] Логирование через `self.log` + `LogEventType` (нет `EventBusLogger` или `print`)
- [ ] `_execute_impl` возвращает данные (не `ExecutionResult`)
- [ ] Есть input и output контракты в `data/contracts/`
- [ ] Есть промпт в `data/prompts/` (если требуется LLM)
- [ ] Версии ресурсов указаны в `ComponentConfig`

### Валидация

- [ ] Пройден `scripts/validation/check_skill_architecture.py`
- [ ] Пройден `scripts/validation/check_yaml_syntax.py`
- [ ] Промпты валидны (нет placeholder `{{input}}` без переменной)
- [ ] BOM-символы удалены (`python scripts/maintenance/remove_bom.py`)

### Тесты

- [ ] Написаны unit-тесты для новой логики
- [ ] Написаны integration-тесты для взаимодействия
- [ ] Пройдены существующие тесты

### Документация

- [ ] Обновлена документация компонента
- [ ] Добавлены примеры использования
- [ ] Обновлен `registry.yaml` (если новый компонент)

---

## 📁 Структура Проекта

```
project_root/
├── core/
│   ├── components/              # Базовые компоненты
│   │   ├── base_component.py    # ← Наследуйся отсюда
│   │   ├── lifecycle.py         # Жизненный цикл
│   │   └── component_discovery.py
│   │
│   ├── application/
│   │   ├── skills/              # Навыки
│   │   │   └── base_skill.py    # ← Наследуйся отсюда
│   │   ├── tools/               # Инструменты
│   │   │   └── base_tool.py     # ← Наследуйся отсюда
│   │   ├── services/            # Сервисы
│   │   │   └── base_service.py  # ← Наследуйся отсюда
│   │   ├── behaviors/           # Паттерны поведения
│   │   │   └── base_behavior_pattern.py
│   │   └── agent/
│   │       └── components/
│   │           ├── action_executor.py  # ← Используй это
│   │           └── behavior_manager.py
│   │
│   ├── config/
│   │   ├── component_config.py  # ← Конфигурация компонента
│   │   └── app_config.py        # ← Конфигурация приложения
│   │
│   └── models/
│       └── data/
│           ├── execution.py     # ← ExecutionResult
│           ├── capability.py    # ← Capability
│           ├── prompt.py        # ← Prompt
│           └── contract.py      # ← Contract
│
├── data/
│   ├── prompts/                 # Промпты
│   │   └── {type}/{component}/
│   └── contracts/               # Контракты
│       └── {type}/{component}/
│
├── scripts/
│   └── validation/
│       ├── check_skill_architecture.py  # ← Запусти перед коммитом
│       └── check_yaml_syntax.py
│
└── docs/
    └── RULES.MD  # ← Этот файл (требования к разработке)
```

---

## 🔧 Инструменты Проверки

### 1. Проверка Архитектуры

```bash
# Проверка нарушений архитектуры в навыках
python scripts/validation/check_skill_architecture.py
```

**Ожидаемый результат:**
```
[OK] Нарушений архитектуры не найдено!
```

### 2. Проверка YAML Синтаксиса

```bash
# Проверка синтаксиса промптов и контрактов
python scripts/validation/check_yaml_syntax.py
```

**Ожидаемый результат:**
```
Checked X files, successful: X, errors: 0
```

### 3. Проверка Соответствия Registry

```bash
# Проверка соответствия файлов в ФС и registry.yaml
python scripts/maintenance/check_consistency.py
```

---

## 📝 Рекомендации по Промптам и Контрактам

### 1. Именование Переменных в Промптах

**ПРАВИЛО:** Имена переменных в промпте должны точно соответствовать передаваемым значениям в коде.

```yaml
# ✅ ПРАВИЛЬНО: переменная observations (множественное число)
content: |
  ## Собранная информация (наблюдения)
  {observations}
variables:
  - name: observations
    description: Список наблюдений
    required: false
    default_value: []

# ❌ НЕПРАВИЛЬНО: переменная observation (единственное число)
content: |
  ## Собранная информация (наблюдения)
  {observation}  ← Ошибка: в коде передаётся observations
```

**Типичные ошибки:**
| Ошибка | Исправление |
|--------|-------------|
| `{observation}` | `{observations}` (список) |
| `{step}` | `{steps_taken}` (список шагов) |
| `{format}` | `{format_type}` |

### 2. Преобразование Типов для Рендеринга

**ПРАВИЛО:** `.format()` в Python требует строки. Списки нужно преобразовывать в строки.

```python
# ✅ ПРАВИЛЬНО: Преобразование списка в строку
observations_str = "\n".join([f"{i}. {obs}" for i, obs in enumerate(observations, 1)])
rendered_prompt = prompt_obj.render(
    goal=goal,
    observations=observations_str,  # ← строка, не список!
    steps_taken=steps_str
)

# ❌ НЕПРАВИЛЬНО: Передача списка напрямую
rendered_prompt = prompt_obj.render(
    goal=goal,
    observations=observations  # ← Ошибка: список не строка
)
```

### 3. Соответствие Полей Контракта и Кода

**ПРАВИЛО:** Имена полей в output контракте должны точно совпадать с кодом извлечения.

```yaml
# output контракт
schema_data:
  type: object
  properties:
    final_answer:
      type: string
      description: Основной финальный ответ
    confidence_score:
      type: number
      description: Уровень уверенности
  required:
    - final_answer
    - confidence_score
```

```python
# ✅ ПРАВИЛЬНО: Извлечение полей согласно контракту
if isinstance(parsed_response, BaseModel):
    final_answer_val = getattr(parsed_response, 'final_answer', '')
    confidence_val = getattr(parsed_response, 'confidence_score', 0.8)
else:
    final_answer_val = parsed_response.get("final_answer", "")
    confidence_val = parsed_response.get("confidence_score", 0.8)

# ❌ НЕПРАВИЛЬНО: Неправильные имена полей
final_answer_val = parsed_response.get("answer", "")  # ← Ошибка: поле final_answer
confidence_val = parsed_response.get("confidence", 0.8)  # ← Ошибка: поле confidence_score
```

### 4. additionalProperties в Контрактах

**ПРАВИЛО:** Всегда указывай `additionalProperties: false` для строгой валидации.

```yaml
# ✅ ПРАВИЛЬНО: Строгая валидация
schema_data:
  type: object
  properties:
    final_answer:
      type: string
    confidence_score:
      type: number
  required:
    - final_answer
    - confidence_score
  additionalProperties: false  # ← Запрет лишних полей

# ❌ НЕПРАВИЛЬНО: Разрешены любые поля
schema_data:
  type: object
  properties:
    final_answer:
      type: string
  # Нет additionalProperties: false
```

### 5. Пример Правильного Промпта

```yaml
# data/prompts/skill/final_answer/final_answer.generate.user_v1.0.0.yaml
capability: final_answer.generate
version: v1.0.0
status: active
content: |
  Ты — интеллектуальный ассистент, который генерирует финальный ответ.

  ## Исходная цель
  {goal}

  ## Собранная информация (наблюдения)
  {observations}

  ## Выполненные шаги
  {steps_taken}

  ## Требования к ответу
  - **Формат вывода**: {format_type}
  - **Включать шаги выполнения**: {include_steps}
  - **Включать источники (доказательства)**: {include_evidence}

  ## Формат ответа
  - Верни ТОЛЬКО валидный JSON согласно выходному контракту
  - Не используй markdown разметку (```json)
  - Не добавляй пояснений до или после JSON
variables:
  - name: goal
    description: Исходная цель
    required: true
  - name: observations
    description: Список наблюдений
    required: false
    default_value: []
  - name: steps_taken
    description: Список выполненных шагов
    required: false
    default_value: []
  - name: format_type
    description: Формат вывода
    required: false
    default_value: detailed
  - name: include_steps
    description: Включать ли шаги
    required: false
    default_value: true
  - name: include_evidence
    description: Включать ли источники
    required: false
    default_value: true
```

### 6. Пример Правильного Системного Промпта

```yaml
# data/prompts/skill/final_answer/final_answer.generate.system_v1.0.0.yaml
capability: final_answer.generate.system
version: v1.0.0
status: active
content: |
  Ты — модуль генерации финального ответа агента.

  == ТВОЯ ЗАДАЧА ==
  Сформируй финальный ответ на основе предоставленного контекста.

  == ВЫХОДНОЙ ФОРМАТ ==
  Верни JSON согласно выходному контракту со следующими полями:
  - final_answer (string, required): Основной ответ пользователю
  - confidence_score (number 0.0-1.0, required): Уровень уверенности
  - sources (array, optional): Список источников
  - summary_of_steps (string, optional): Краткое резюме шагов
  - remaining_questions (array, optional): Нерешённые вопросы

  == КРИТИЧНЫЕ ПРАВИЛА ==
  1. Верни ТОЛЬКО чистый JSON без markdown разметки
  2. Не добавляй никаких пояснений до или после JSON
  3. Поле final_answer должно содержать полный ответ на цель
  4. confidence_score должен отражать реальную уверенность (0.9+ для точных данных)

  == ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА ==
  {
    "final_answer": "Пушкин написал 5 книг: Евгений Онегин, Капитанская дочка...",
    "confidence_score": 0.99,
    "sources": ["Евгений Онегин (1833)", "Капитанская дочка (1836)"],
    "summary_of_steps": "Выполнен поиск книг по автору",
    "remaining_questions": []
  }
variables: []
```

---

## 📚 Дополнительные Ресурсы

| Документ | Описание |
|----------|----------|
| `docs/RULES.MD` | Требования к разработке (этот файл) |
| `docs/architecture/ideal.md` | Целевая архитектура системы |
| `docs/architecture/checklist.md` | Чек-лист зрелости архитектуры |
| `docs/architecture/lifecycle.md` | Жизненный цикл компонентов |
| `docs/components/README.md` | Документация компонентов |
| `docs/guides/README.md` | Практические руководства |
| `docs/logging/README.md` | Система логирования |
| `docs/vector_search/README.md` | Векторный поиск |

---

## ❓ FAQ

### Q: Можно ли создать новый базовый класс?

**A:** Только если:
1. Существующие (`BaseSkill`/`BaseTool`/`BaseService`) не подходят
2. Есть уникальные требования к жизненному циклу
3. Обосновано в PR с шаблоном из раздела "Обоснование Новых Абстракций"

### Q: Можно ли использовать прямой доступ к БД?

**A:** Нет. Всегда через:
```python
await self.executor.execute_action(
    action_name="sql_tool.execute",
    parameters={"query": "..."},
    context=execution_context
)
```

### Q: Можно ли использовать `print` для отладки?

**A:** Нет. Используй:
```python
self._log_debug("Сообщение")  # только файл
self._log_info("Сообщение", event_type=LogEventType.USER_PROGRESS)  # терминал + файл
```

### Q: Как добавить новую зависимость компонента?

**A:** Через `DEPENDENCIES`:
```python
class MySkill(BaseSkill):
    DEPENDENCIES = ["sql_tool", "prompt_service", "new_dependency"]
```

### Q: Как проверить что компонент инициализирован?

**A:** Через состояние:
```python
if self._state == ComponentState.READY:
    # Компонент готов
    pass

# Или через метод
self.ensure_ready()  # Бросит RuntimeError если не готов
```

### Q: Можно ли создать миксин для логирования?

**A:** Нет, это избыточно. Все компоненты наследуют `Component` (через `LoggingMixinV2`), который предоставляет:
- `self._log_info()`, `self._log_debug()`, `self._log_warning()`, `self._log_error()`
- `self._safe_log_sync()` — безопасный синхронный лог
- Каждый вызов автоматически получает `event_type` (по умолчанию `LogEventType.INFO`)
- Для переопределения: `self._log_info("...", event_type=LogEventType.USER_PROGRESS)`

---

## 📈 Метрики Качества Кода

| Метрика | Требование | Как Проверить |
|---------|------------|---------------|
| Нарушения архитектуры | 0 | `check_skill_architecture.py` |
| Ошибки YAML синтаксиса | 0 | `check_yaml_syntax.py` |
| Прямой доступ к компонентам | 0 | AST-анализ |
| Возврат ExecutionResult из `_execute_impl` | 0 | AST-анализ |
| Прямые вызовы LLM API | 0 | Pattern search |
| Retry логика в навыках | 0 | Pattern search |
| BOM-символы в файлах | 0 | `scripts/maintenance/remove_bom.py` |

---

## ✨ Рекомендации для Чистоты Проекта

### 1. Используй Type Hints

```python
# ✅ ПРАВИЛЬНО
async def _execute_impl(
    self,
    capability: 'Capability',
    parameters: Dict[str, Any],
    execution_context: 'ExecutionContext'
) -> Dict[str, Any]:
```

### 2. Документируй Capability

```python
def get_capabilities(self) -> List[Capability]:
    """
    Возвращает список capability навыка.
    
    CAPABILITIES:
    - my_skill.do_something - описание
    - my_skill.do_other - описание
    """
```

### 3. Используй Константы для Имен Действий

```python
# ✅ ПРАВИЛЬНО
class ActionNames:
    SQL_EXECUTE = "sql_tool.execute"
    LLM_GENERATE = "llm.generate"

# Вместо хардкода строк
await self.executor.execute_action(ActionNames.SQL_EXECUTE, ...)
```

### 4. Группируй Зависимости

```python
# ✅ ПРАВИЛЬНО
DEPENDENCIES = [
    # Infrastructure
    "sql_tool",
    "prompt_service",
    
    # Services
    "table_description_service",
]
```

### 5. Валидируй Настройки в `__init__`

```python
def __init__(self, name, application_context, component_config, executor):
    super().__init__(name, application_context, component_config, executor)
    
    # Валидация обязательных настроек
    if not hasattr(self.component_config, 'variant_id'):
        raise ValueError("component_config требует variant_id")
```

---

> **Помни:** Цель этих требований — не ограничить творчество, а обеспечить согласованность архитектуры и предотвратить дублирование функциональности. Если видишь способ улучшить существующую абстракцию — предлагай через PR с обоснованием!