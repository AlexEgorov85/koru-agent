# Требования к Разработке Агента — Agent v5

> **Версия:** 5.2.0
> **Статус:** Active
> **Дата обновления:** 2026-03-12
> **Владелец:** @system
> **Последние изменения:** Удалён избыточный LoggingMixin, логирование напрямую в BaseComponent

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
| **Используй EventBusLogger** | Логирование ТОЛЬКО через `self.event_bus_logger` | `await self.event_bus_logger.info(...)` |
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
| `DataRepository` | `core/application/data_repository.py` | Централизованный репозиторий промптов и контрактов |
| `ComponentRegistry` | `core/application/registry/component_registry.py` | Реестр компонентов |
| `ResourceDiscovery` | `core/infrastructure/discovery/resource_discovery.py` | Авто-обнаружение ресурсов |

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
    await self.event_bus_logger.info(f"{self.name} инициализирован")
    
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

**НЕ ДЕЛАЙ:**
```python
# ❌ ЗАПРЕЩЕНО: Стандартный logging
import logging
logger = logging.getLogger(__name__)
logger.info("Message")

# ❌ ЗАПРЕЩЕНО: Print
print("Debug message")
```

**ДЕЛАЙ:**
```python
# ✅ ПРАВИЛЬНО: EventBusLogger
await self.event_bus_logger.info("Сообщение")
await self.event_bus_logger.debug("Отладка", extra={"key": "value"})
await self.event_bus_logger.warning("Предупреждение")
await self.event_bus_logger.error("Ошибка", exc_info=True)

# ✅ ПРАВИЛЬНО: Синхронная версия (во время инициализации)
self.event_bus_logger.info_sync("Сообщение")
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
- [ ] Логирование через `EventBusLogger` (нет `logging` или `print`)
- [ ] `_execute_impl` возвращает данные (не `ExecutionResult`)
- [ ] Есть input и output контракты в `data/contracts/`
- [ ] Есть промпт в `data/prompts/` (если требуется LLM)
- [ ] Версии ресурсов указаны в `ComponentConfig`

### Валидация

- [ ] Пройден `scripts/validation/check_skill_architecture.py`
- [ ] Пройден `scripts/validation/check_yaml_syntax.py`
- [ ] Промпты валидны (нет placeholder `{{input}}` без переменной)

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
    └── ARCHITECTURE_REQUIREMENTS.md  # ← Этот файл
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

## 📚 Дополнительные Ресурсы

| Документ | Описание |
|----------|----------|
| `docs/ARCHITECTURE.md` | Общая архитектура системы |
| `docs/COMPONENT_GUIDE.md` | Руководство по созданию компонентов |
| `docs/CONTRACTS.md` | Руководство по контрактам |
| `docs/PROMPTS.md` | Руководство по промптам |
| `docs/TESTING.md` | Руководство по тестированию |

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
await self.event_bus_logger.debug("Сообщение", extra={"key": "value"})
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

## 📞 Контакты

| Вопрос | Куда Обратиться |
|--------|-----------------|
| Архитектурные вопросы | @system (через PR review) |
| Технические вопросы | docs/ARCHITECTURE.md |
| Ошибки валидации | scripts/validation/ |
| Предложения улучшений | Создать issue с шаблоном "Обоснование Новых Абстракций" |

---

> **Помни:** Цель этих требований — не ограничить творчество, а обеспечить согласованность архитектуры и предотвратить дублирование функциональности. Если видишь способ улучшить существующую абстракцию — предлагай через PR с обоснованием!