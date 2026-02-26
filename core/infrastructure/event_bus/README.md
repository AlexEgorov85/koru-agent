# 📡 Event Bus — Разделение на доменные шины

## 📋 Обзор

Модуль `domain_event_bus.py` реализует **менеджер доменных шин событий** для изоляции компонентов системы.

## 🎯 Проблемы, которые решает

### До рефакторинга:
```python
# Одна глобальная шина для всего
_global_event_bus = EventBus()

# Все события смешиваются:
await event_bus.publish(EventType.AGENT_CREATED, {...})      # Агент
await event_bus.publish(EventType.BENCHMARK_STARTED, {...})  # Бенчмарк
await event_bus.publish(EventType.LLM_CALL_FAILED, {...})    # Инфраструктура

# Проблемы:
# ❌ Сильное耦合 между компонентами
# ❌ Сложно отладить поток событий
# ❌ Невозможно изолировать домены
```

### После рефакторинга:
```python
# Раздельные шины по доменам
event_bus_manager = EventBusManager()

agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
benchmark_bus = event_bus_manager.get_bus(EventDomain.BENCHMARK)
infra_bus = event_bus_manager.get_bus(EventDomain.INFRASTRUCTURE)

# Изолированная публикация
await agent_bus.publish(EventType.AGENT_CREATED, {...})
await benchmark_bus.publish(EventType.BENCHMARK_STARTED, {...})
await infra_bus.publish(EventType.LLM_CALL_FAILED, {...})

# Преимущества:
# ✅ Изоляция доменов
# ✅ Легче отладка
# ✅ Можно отключать домены независимо
```

## 🏗️ Архитектура

```
EventBusManager
├── DomainEventBus[AGENT]
│   ├── AGENT_CREATED
│   ├── AGENT_STARTED
│   └── ...
├── DomainEventBus[BENCHMARK]
│   ├── BENCHMARK_STARTED
│   ├── BENCHMARK_COMPLETED
│   └── ...
├── DomainEventBus[INFRASTRUCTURE]
│   ├── LLM_CALL_STARTED
│   ├── PROVIDER_REGISTERED
│   └── ...
├── DomainEventBus[OPTIMIZATION]
│   ├── VERSION_CREATED
│   └── ...
└── DomainEventBus[SECURITY]
    ├── SECURITY_AUDIT
    └── ...
```

## 📖 Использование

### 1. Базовое использование

```python
from core.infrastructure.event_bus import (
    EventBusManager,
    EventDomain,
    EventType,
    get_event_bus_manager
)

# Получение менеджера (singleton)
event_bus_manager = get_event_bus_manager()

# Получение шины конкретного домена
agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)

# Подписка на событие
async def on_agent_created(event):
    print(f"Агент создан: {event.data}")

agent_bus.subscribe(EventType.AGENT_CREATED, on_agent_created)

# Публикация события
await agent_bus.publish(
    EventType.AGENT_CREATED,
    data={"agent_id": "123", "goal": "Поиск книг"},
    source="agent_factory"
)
```

### 2. Кросс-доменные события

```python
# Публикация в несколько доменов одновременно
result = await event_bus_manager.publish_cross_domain(
    EventType.SYSTEM_INITIALIZED,
    domains=[EventDomain.INFRASTRUCTURE, EventDomain.AGENT],
    data={"version": "1.0.0"},
    source="main"
)

# Результат:
# {"infrastructure": True, "agent": True}
```

### 3. Глобальная подписка на все события

```python
async def global_event_handler(event: DomainEvent):
    print(f"Событие: {event.event_type}, Домен: {event.domain.value}")

event_bus_manager.subscribe_all(global_event_handler)
```

### 4. Включение/выключение доменов

```python
# Отключение домена бенчмарков (например, для prod)
event_bus_manager.disable_domain(EventDomain.BENCHMARK)

# Включение домена
event_bus_manager.enable_domain(EventDomain.BENCHMARK)

# Проверка статуса
stats = event_bus_manager.get_all_stats()
print(stats["domains"]["benchmark"]["enabled"])  # True/False
```

### 5. Статистика по доменам

```python
stats = event_bus_manager.get_all_stats()

# Пример вывода:
# {
#     "domains": {
#         "agent": {
#             "domain": "agent",
#             "enabled": True,
#             "event_count": 150,
#             "error_count": 2,
#             "subscribers_count": 5
#         },
#         "benchmark": {...},
#         "infrastructure": {...}
#     },
#     "global_subscribers_count": 1,
#     "cross_domain_listeners_count": 0
# }
```

## 🔧 Интеграция с существующим кодом

### Обновление main.py

```python
# Было:
from core.infrastructure.event_bus import get_event_bus
event_bus = get_event_bus()

# Стало (рекомендуется):
from core.infrastructure.event_bus import get_event_bus_manager, EventDomain
event_bus_manager = get_event_bus_manager()

# Для агента используем домен AGENT
agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)

# Для инфраструктурных событий
infra_bus = event_bus_manager.get_bus(EventDomain.INFRASTRUCTURE)
```

### Обновление подписчиков

```python
# Было:
from core.infrastructure.event_bus import get_event_bus

event_bus = get_event_bus()
event_bus.subscribe(EventType.AGENT_CREATED, handler)

# Стало:
from core.infrastructure.event_bus import get_event_bus_manager, EventDomain

event_bus_manager = get_event_bus_manager()
agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
agent_bus.subscribe(EventType.AGENT_CREATED, handler)
```

### Обратная совместимость

```python
# Старый код продолжает работать:
from core.infrastructure.event_bus import get_event_bus

event_bus = get_event_bus()  # Возвращает шину домена COMMON
event_bus.subscribe(EventType.ERROR_OCCURRED, handler)
```

## 📊 Маппинг событий на домены

| Домен | События |
|-------|---------|
| **AGENT** | AGENT_CREATED, AGENT_STARTED, AGENT_COMPLETED, AGENT_FAILED, CAPABILITY_SELECTED, SKILL_EXECUTED, ACTION_PERFORMED, STEP_REGISTERED, CONTEXT_ITEM_ADDED, PLAN_CREATED, PLAN_UPDATED |
| **BENCHMARK** | BENCHMARK_STARTED, BENCHMARK_COMPLETED, BENCHMARK_FAILED |
| **INFRASTRUCTURE** | SYSTEM_INITIALIZED, SYSTEM_SHUTDOWN, SYSTEM_ERROR, PROVIDER_REGISTERED, PROVIDER_UNREGISTERED, LLM_CALL_*, SERVICE_*, COMPONENT_* |
| **OPTIMIZATION** | OPTIMIZATION_CYCLE_*, VERSION_* |
| **SECURITY** | SECURITY_AUDIT (новое) |
| **COMMON** | ERROR_OCCURRED, RETRY_ATTEMPT, METRIC_COLLECTED, EXECUTION_* |

## 🧪 Тестирование

```python
import pytest
from core.infrastructure.event_bus import (
    EventBusManager,
    EventDomain,
    EventType,
    reset_event_bus_manager
)

@pytest.fixture
def event_bus_manager():
    """Фикстура для тестов"""
    reset_event_bus_manager()  # Сброс singleton
    manager = EventBusManager()
    yield manager
    reset_event_bus_manager()  # Очистка после теста

async def test_domain_isolation(event_bus_manager):
    """Тест изоляции доменов"""
    agent_events = []
    benchmark_events = []
    
    agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
    benchmark_bus = event_bus_manager.get_bus(EventDomain.BENCHMARK)
    
    agent_bus.subscribe(EventType.AGENT_CREATED, lambda e: agent_events.append(e))
    benchmark_bus.subscribe(EventType.BENCHMARK_STARTED, lambda e: benchmark_events.append(e))
    
    # Публикация в разные домены
    await agent_bus.publish(EventType.AGENT_CREATED, {})
    await benchmark_bus.publish(EventType.BENCHMARK_STARTED, {})
    
    # Проверка изоляции
    assert len(agent_events) == 1
    assert len(benchmark_events) == 1
    assert agent_events[0].event_type == EventType.AGENT_CREATED.value
    assert benchmark_events[0].event_type == EventType.BENCHMARK_STARTED.value
```

## ⚠️ Миграция

### Этапы миграции:

1. **Этап 1 (неделя 1)**: Параллельная работа
   - Новый код использует `EventBusManager`
   - Старый код продолжает использовать `get_event_bus()`
   - Тестирование изоляции доменов

2. **Этап 2 (неделя 2)**: Постепенная миграция
   - Обновление `main.py` для использования менеджера
   - Обновление подписчиков LLM
   - Обновление обработчиков метрик

3. **Этап 3 (неделя 3)**: Завершение
   - Удаление устаревших вызовов
   - Включение всех доменов в prod
   - Мониторинг производительности

## 📈 Метрики для мониторинга

После внедрения отслеживайте:

1. **event_count** по доменам — равномерность распределения
2. **error_count** — ошибки в обработчиках
3. **subscribers_count** — количество подписчиков
4. **Время обработки** событий — не должно увеличиться

## 🔗 Связанные документы

- `core/infrastructure/event_bus/event_bus.py` — базовый класс
- `core/infrastructure/event_bus/event_handlers.py` — обработчики
- `tests/unit/event_bus/test_domain_event_bus.py` — тесты
