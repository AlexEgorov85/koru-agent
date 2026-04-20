# Жизненный цикл компонентов

**Версия:** 5.41.0  
**Дата:** 17 апреля 2026 г.

---

## 1. Обзор

Система управления жизненным циклом компонентов обеспечивает предсказуемую инициализацию, работу и завершение всех компонентов агента.

---

## 2. Состояния компонента

**Enum:** `core/models/enums/component_status.py`

```python
from core.models.enums.component_status import ComponentStatus

class ComponentStatus(Enum):
    CREATED = "created"       # Экземпляр создан, но не инициализирован
    INITIALIZING = "initializing"  # В процессе инициализации
    READY = "ready"          # Готов к работе
    FAILED = "failed"        # Ошибка инициализации
    SHUTDOWN = "shutdown"    # Корректно завершён
```

---

## 3. Базовые классы

### 3.1. ComponentLifecycle

**Файл:** `core/agent/components/lifecycle.py`

```python
from core.agent.components.lifecycle import ComponentLifecycle
from core.models.enums.component_status import ComponentStatus

class MyComponent(ComponentLifecycle):
    def __init__(self, name: str):
        super().__init__(name)
    
    async def _do_init(self):
        # Инициализация ресурсов
        pass
    
    async def some_method(self):
        self.ensure_ready()  # Проверка готовности
        # Бизнес-логика
```

### 3.2. Публичные методы

| Метод | Описание |
|-------|----------|
| `ensure_ready()` | Проверяет состояние READY, выбрасывает RuntimeError если не готов |
| `status` (property) | Текущий статус компонента |
| `is_ready` (property) | Проверка: статус READY |
| `is_initialized` (property) | Проверка: READY или SHUTDOWN |
| `is_failed` (property) | Проверка: статус FAILED |

---

## 4. Иерархия наследования

```
ComponentLifecycle (core/agent/components/lifecycle.py)
    │
    └── BaseComponent (core/agent/components/component.py)
            │
            ├── BaseSkill
            ├── BaseTool
            └── BaseService
```

**InfrastructureContext** и **ApplicationContext** используют состояния напрямую.

---

## 5. Порядок инициализации

```python
# 1. InfrastructureContext
infra = InfrastructureContext(config)
await infra.initialize()
assert infra.is_ready

# 2. ApplicationContext  
app = ApplicationContext(infra, app_config)
await app.initialize()
assert app.is_ready

# 3. AgentRuntime (проверяет готовность контекстов автоматически)
agent = AgentRuntime(app, goal="...")
await agent.run()
```

---

## 6. Файлы

| Файл | Описание |
|------|----------|
| `core/agent/components/lifecycle.py` | ComponentLifecycle |
| `core/agent/components/component.py` | BaseComponent |
| `core/infrastructure_context/infrastructure_context.py` | InfrastructureContext |
| `core/application_context/application_context.py` | ApplicationContext |
| `core/models/enums/component_status.py` | ComponentStatus enum |

---

## 7. Связанная документация

- [AGENTS.md](../../AGENTS.md) — правила разработки
- [ideal.md](ideal.md) — целевая архитектура
- [checklist.md](checklist.md) — проверка зрелости
