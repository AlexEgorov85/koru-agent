# Жизненный цикл компонентов

**Версия:** 1.0  
**Дата:** 6 марта 2026 г.

---

## 1. Обзор

Система управления жизненным циклом компонентов обеспечивает предсказуемую инициализацию, работу и завершение всех компонентов агента.

---

## 2. Состояния компонента

```
┌──────────┐    initialize()    ┌──────────────┐
│  CREATED │ ──────────────────>│ INITIALIZING │
└──────────┘                    └──────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
              success()         error raised      shutdown()
                    │                │                │
                    ▼                ▼                ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  READY   │   │  FAILED  │   │ SHUTDOWN │   │  FAILED  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### 2.1. Описание состояний

| Состояние | Описание |
|-----------|----------|
| `CREATED` | Экземпляр создан, но не инициализирован |
| `INITIALIZING` | В процессе инициализации |
| `READY` | Готов к работе (все ресурсы загружены) |
| `FAILED` | Ошибка инициализации (требуется вмешательство) |
| `SHUTDOWN` | Корректно завершён |

---

## 3. Базовые классы

### 3.1. LifecycleMixin

**Файл:** `core/components/lifecycle.py`

```python
from core.components.lifecycle import LifecycleMixin, ComponentState

class MyComponent(LifecycleMixin):
    def __init__(self, name: str):
        super().__init__(name)
    
    async def initialize(self):
        await self._transition_to(ComponentState.INITIALIZING)
        try:
            # Инициализация
            await self._do_init()
            await self._transition_to(ComponentState.READY)
        except Exception as e:
            await self._transition_to(ComponentState.FAILED)
            raise
    
    def do_something(self):
        self.ensure_ready()  # Проверка готовности
        # Бизнес-логика
```

### 3.2. Публичные методы

| Метод | Описание |
|-------|----------|
| `ensure_ready()` | Проверяет состояние READY, выбрасывает RuntimeError если не готов |
| `state` (property) | Текущее состояние компонента |
| `is_ready` (property) | Проверка: состояние READY |
| `is_initialized` (property) | Проверка: READY или SHUTDOWN |
| `is_failed` (property) | Проверка: FAILED |

---

## 4. Иерархия наследования

```
LifecycleMixin
    │
    └── BaseComponent
            │
            ├── BaseSkill
            ├── BaseTool
            └── BaseService
```

**InfrastructureContext** и **ApplicationContext** используют состояния напрямую (не наследуют LifecycleMixin).

---

## 5. Порядок инициализации

### 5.1. Правильный порядок

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

### 5.2. Проверки в AgentRuntime

`AgentRuntime.__init__()` автоматически проверяет:
- `application_context.is_ready == True`
- `infrastructure_context.is_ready == True`

Если не готовы → выбрасывает `RuntimeError`.

---

## 6. Обработка ошибок

### 6.1. Ошибка инициализации

```python
try:
    await component.initialize()
except Exception as e:
    # component.state == ComponentState.FAILED
    print(f"Component failed: {component.state}")
```

### 6.2. Использование до инициализации

```python
component = MyComponent("test")
component.do_something()  # ❌ RuntimeError: not ready

await component.initialize()
component.do_something()  # ✅ OK
```

---

## 7. Завершение работы

### 7.1. Порядок завершения

```python
# Обратный порядок инициализации
await agent.stop()
await application_context.shutdown()
await infrastructure_context.shutdown()
await shutdown_logging_system()
```

### 7.2. Состояния при shutdown

```python
await context.shutdown()
assert context.state == ComponentState.SHUTDOWN
```

---

## 8. Диагностика

### 8.1. Проверка состояния

```python
print(f"State: {component.state}")           # ComponentState.READY
print(f"Is ready: {component.is_ready}")     # True
print(f"Is failed: {component.is_failed}")   # False
```

### 8.2. Логирование состояний

Все переходы состояний логируются через `_publish_with_context()`:
- `"Начало инициализации {component_name}"`
- `"Компонент '{name}' полностью инициализирован"`
- `"Ошибка инициализации компонента '{name}'"`

Контекст session_id/agent_id автоматически устанавливается в `BaseComponent.execute()`.

---

## 9. Миграция со старого кода

### 9.1. Было

```python
# Старый код
if not self._initialized:
    raise RuntimeError("Not initialized")

self._initialized = True
```

### 9.2. Стало

```python
# Новый код
self.ensure_ready()  # Автоматическая проверка

await self._transition_to(ComponentState.READY)
```

---

## 10. Лучшие практики

### ✅ Делайте

- Вызывайте `ensure_ready()` в начале публичных методов
- Проверяйте `is_ready` перед использованием компонента
- Обрабатывайте состояние `FAILED`
- Логируйте переходы состояний

### ❌ Не делайте

- Не игнорируйте ошибки инициализации
- Не используйте компоненты до `initialize()`
- Не меняйте состояние напрямую (используйте `_transition_to()`)
- Не вызывайте `initialize()` повторно без проверки

---

## 11. Тестирование

### 11.1. Юнит-тест

```python
import pytest
from core.components.lifecycle import ComponentState

async def test_component_states():
    component = TestComponent("test")
    
    # Проверка начального состояния
    assert component.state == ComponentState.CREATED
    assert not component.is_ready
    
    # Проверка ошибки до инициализации
    with pytest.raises(RuntimeError):
        component.ensure_ready()
    
    # Инициализация
    await component.initialize()
    assert component.state == ComponentState.READY
    assert component.is_ready
    
    # Использование после инициализации
    component.ensure_ready()  # Не выбрасывает
```

---

## 12. Приложения

### A. Список файлов

| Файл | Описание |
|------|----------|
| `core/components/lifecycle.py` | Базовые классы и enum |
| `core/components/base_component.py` | Базовый компонент |
| `core/infrastructure/context/infrastructure_context.py` | Инфраструктурный контекст |
| `core/application/context/application_context.py` | Прикладной контекст |

### B. Связанная документация

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [COMPONENTS_GUIDE.md](./COMPONENTS_GUIDE.md)
- [TESTING.md](./TESTING.md)
