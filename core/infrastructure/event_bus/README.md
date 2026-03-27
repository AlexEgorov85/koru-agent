# 📡 Unified Event Bus

## 📋 Обзор

Модуль `unified_event_bus.py` реализует **единую шину событий** с поддержкой:
- Session isolation (изоляция по сессиям)
- Domain routing (маршрутизация по доменам)
- FIFO порядок внутри сессии
- Backpressure (ограничение размера очереди)

## 🎯 Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedEventBus                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Session Workers (изолированные очереди)              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │Session A│ │Session B│ │Session C│ │  ...    │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Domain Routing (внутри одной шины)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  event.domain → фильтр подписчиков                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📖 Использование

### 1. Базовое использование

```python
from core.infrastructure.event_bus import (
    get_event_bus,
    EventType,
    EventDomain
)

# Получение шины (singleton)
event_bus = get_event_bus()

# Подписка на событие
async def on_agent_started(event):
    print(f"Агент запущен: {event.data}")

event_bus.subscribe(EventType.AGENT_STARTED, on_agent_started)

# Публикация события
await event_bus.publish(
    EventType.AGENT_STARTED,
    data={"agent_id": "123", "goal": "Поиск книг"},
    session_id="session_123",
    domain=EventDomain.AGENT
)
```

### 2. Подписка с фильтрами

```python
# Подписка с фильтром по домену
event_bus.subscribe(
    EventType.AGENT_STARTED,
    handler,
    domain=EventDomain.AGENT
)

# Подписка с фильтром по сессии
event_bus.subscribe(
    EventType.AGENT_STARTED,
    handler,
    session_id="session_123"
)

# Глобальная подписка с фильтром по доменам
event_bus.subscribe_all(
    handler,
    domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE]
)
```

### 3. Логирование через EventBusLogger (deprecated)

> ⚠️ **Рекомендуется использовать прямые вызовы `event_bus.publish()` вместо EventBusLogger**

```python
from core.infrastructure.event_bus.unified_logger import EventBusLogger

logger = EventBusLogger(
    event_bus=event_bus,
    session_id="session_123",
    agent_id="agent_001",
    component="MyComponent"
)

# Логирование
await logger.info("Компонент инициализирован")
await logger.debug("Детали: %s", details)
await logger.warning("Предупреждение")
await logger.error("Ошибка: %s", error)
```

### 4. Рекомендуемый способ логирования

```python
# Вместо EventBusLogger используйте:
await event_bus.publish(
    EventType.AGENT_STARTED,
    data={"agent_id": "123", "message": "Агент запущен"},
    session_id="session_123",
    domain=EventDomain.AGENT
)
```

## 🏷️ Домены событий

| Домен | Описание | Примеры событий |
|-------|----------|-----------------|
| `AGENT` | События агента | AGENT_CREATED, AGENT_STARTED |
| `BENCHMARK` | События бенчмарков | BENCHMARK_STARTED, BENCHMARK_COMPLETED |
| `INFRASTRUCTURE` | Инфраструктурные события | LLM_CALL_STARTED, PROVIDER_REGISTERED |
| `OPTIMIZATION` | События оптимизации | VERSION_CREATED, VERSION_PROMOTED |
| `SECURITY` | События безопасности | SECURITY_AUDIT |
| `COMMON` | Общие события | ERROR_OCCURRED, METRIC_COLLECTED |

## 📊 Статистика

```python
# Получить статистику шины
stats = event_bus.get_stats()
print(stats)
# {
#     "running": True,
#     "active_sessions": 5,
#     "active_workers": 5,
#     "subscribers_count": 10,
#     "sessions": {...}
# }

# Получить статистику миграции
migration_stats = event_bus.get_migration_stats()
print(migration_stats)
# {
#     "duplicate_subscription_count": 0,
#     "duplicate_warning_threshold": 10,
#     "migration_active": True
# }
```

## 🔧 Конфигурация

```python
from core.infrastructure.event_bus import create_event_bus

# Создание новой шины с настройками
event_bus = create_event_bus(
    queue_max_size=1000,        # Максимум событий в очереди
    worker_idle_timeout=60.0,   # Таймаут простоя worker'а
    subscriber_timeout=30.0     # Таймаут выполнения подписчика
)
```

## 🚀 Миграция со старого API

### Было (EventBusManager):
```python
from core.infrastructure.event_bus.domain_event_bus import get_event_bus_manager

manager = get_event_bus_manager()
agent_bus = manager.get_bus(EventDomain.AGENT)
agent_bus.subscribe(EventType.AGENT_STARTED, handler)
await agent_bus.publish(EventType.AGENT_STARTED, {"agent_id": "123"})
```

### Стало (UnifiedEventBus):
```python
from core.infrastructure.event_bus import get_event_bus, EventDomain

event_bus = get_event_bus()
event_bus.subscribe(
    EventType.AGENT_STARTED,
    handler,
    domain=EventDomain.AGENT
)
await event_bus.publish(
    EventType.AGENT_STARTED,
    data={"agent_id": "123"},
    session_id="session_123",
    domain=EventDomain.AGENT
)
```

## 📝 Примечания

1. **Session ID обязателен** для публикации событий (для маршрутизации)
2. **Domain определяется автоматически** по типу события, но можно указать явно
3. **FIFO порядок** гарантируется только внутри одной сессии
4. **Backpressure** — при переполнении очереди публикация блокируется

## 🧪 Тестирование

```bash
# Запуск тестов
pytest tests/unit/infrastructure/test_unified_event_bus.py -v

# Нагрузочный тест
python scripts/performance/event_bus_benchmark.py
```

## 📚 Ссылки

- [План миграции](../../../../docs/EVENT_BUS_MIGRATION.md)
- [Migration Report](../../../../docs/reports/MIGRATION_REPORT.md)
