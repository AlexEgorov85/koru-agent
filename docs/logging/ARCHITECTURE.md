# Система логирования через EventBus

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     Компоненты приложения                       │
│  (используют EventBusLogger для публикации логов)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  EventBusLogger │  ← logger.py (ЕДИНЫЙ API)
                    │  (публикация)   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    EventBus     │
                    └─────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌──────────────┐
    │ TerminalHandler │ │FileHandler│ │LogCollector  │
    │ (форматирование)│ │(ротация)  │ │(для обучения)│
    └─────────────────┘ └───────────┘ └──────────────┘
```

## Структура модулей

```
core/infrastructure/logging/
├── __init__.py          # Публичный API, экспорт всех компонентов
├── config.py            # Конфигурация (LoggingConfig, TerminalOutputConfig, FileOutputConfig)
├── logger.py            # EventBusLogger - единый API для публикации логов
├── handlers.py          # Обработчики (TerminalLogHandler, FileLogHandler)
├── log_config.py        # Конфигурация хранения и ротации (Legacy, для обратной совместимости)
├── log_search.py        # Поиск по логам
└── log_indexer.py       # Индексация сессий
```

## ⚠️ Миграция на Event Bus (в процессе)

> **Текущий статус:** В проекте добавлены TODO-комментарии для постепенной миграции. Полный переход на `event_bus.publish()` вместо `EventBusLogger` запланирован на будущее.

### Цель миграции

Убрать промежуточный слой `EventBusLogger` и публиковать события напрямую через `event_bus.publish()`:

```python
# Было (через EventBusLogger):
await logger.info("Агент запущен")

# Станет (напрямую через event_bus):
await event_bus.publish(
    EventType.AGENT_STARTED,
    data={"message": "Агент запущен"},
    session_id=session_id
)
```

### Преимущества

- Единый интерфейс для всех событий
- Семантические типы событий (EventType) вместо generic логов
- Возможность подписываться на конкретные типы событий
- Архитектура становится более event-driven

### Скрипты для миграции

В проекте есть скрипты для помощи миграции:

```bash
# Найти все места с логированием
python scripts/find_logging_issues.py

# Добавить TODO-комментарии (уже выполнено)
python scripts/add_logging_todos.py
python scripts/add_eventbuslogger_todos.py
```

### Результаты

- ✅ Добавлено **1300+ TODO-комментариев** в **65+ файлах**
- ⏳ Миграция в процессе (ручная замена по TODO)
- 📊 Все изменения закоммичены в `f17cbc2`

## Удалённые файлы (рефакторинг)

- ❌ `core/infrastructure/logging/event_bus_log_handler.py` - дублировал функциональность
- ❌ `core/infrastructure/logging/log_formatter.py` - legacy для обратной совместимости
- ❌ `core/infrastructure/event_bus/unified_logger.py` - дублировал EventBusLogger

## Быстрое начало

### 1. Базовое использование в компоненте

```python
from core.infrastructure.logging import EventBusLogger

class MyComponent:
    def __init__(self, event_bus, session_id, agent_id):
        self.logger = EventBusLogger(
            event_bus, 
            session_id=session_id, 
            agent_id=agent_id, 
            component="MyComponent"
        )
    
    async def do_something(self):
        await self.logger.info("Запуск процесса")
        await self.logger.debug("Детали: %s", {"key": "value"})
        
        try:
            # ... код ...
            pass
        except Exception as e:
            await self.logger.exception("Ошибка выполнения", exc=e)
```

### 2. Использование фабрики

```python
from core.infrastructure.logging import create_logger

logger = create_logger(
    event_bus=event_bus,
    session_id="session_123",
    agent_id="agent_001",
    component="MyComponent"
)

await logger.info("Сообщение")
```

### 3. Глобальный логгер (для простых случаев)

```python
from core.infrastructure.logging import init_logging_system, get_global_logger

# Инициализация
await init_logging_system(event_bus, session_id="my_session")

# Получение логгера
logger = get_global_logger()
await logger.info("Сообщение")
```

## Конфигурация

### По умолчанию (в InfrastructureContext)

При инициализации `InfrastructureContext` автоматически настраивается логирование:

```python
# В core/infrastructure/context/infrastructure_context.py
log_config = LoggingConfig(
    terminal=TerminalOutputConfig(
        enabled=True,
        level=LogLevel.INFO,      # Только INFO и выше
        format=LogFormat.COLORED, # С цветами и иконками
        show_debug=False,         # DEBUG скрыты
        show_source=True,         # Показывать компонент
        show_session_info=False,  # Не показывать session/agent
    ),
    file=FileOutputConfig(
        enabled=True,
        level=LogLevel.DEBUG,     # В файлы пишется всё
        format=LogFormat.JSONL,   # JSON Lines
        max_file_size_mb=100,
        backup_count=10,
    )
)
```

**Что выводится в терминал:**
- ✅ INFO, WARNING, ERROR, CRITICAL
- ❌ DEBUG (скрыт по умолчанию)
- ✅ С цветами и иконками
- ✅ С именем компонента

**Что пишется в файлы:**
- ✅ ВСЁ (DEBUG и выше)
- ✅ В формате JSONL (удобно для анализа)

### Настройка фильтров

Чтобы изменить, что выводится в терминал:

```python
from core.infrastructure.logging import (
    LoggingConfig,
    TerminalOutputConfig,
    LogLevel,
    LogFormat,
    configure_logging
)

config = LoggingConfig(
    terminal=TerminalOutputConfig(
        enabled=True,
        level=LogLevel.INFO,          # Уровень для терминала
        format=LogFormat.COLORED,     # COLORED, SIMPLE, DETAILED
        show_debug=False,             # Показывать DEBUG сообщения
        show_source=True,             # Показывать имя компонента
        show_session_info=False,      # Показывать session_id и agent_id
        # Фильтры по компонентам
        include_components={"LLMProvider", "Agent"},  # Только эти
        exclude_components={"DebugTool"},             # Кроме этих
        # Фильтры по типам событий
        include_event_types={"log.info", "log.error"},
        exclude_event_types={"log.debug"},
    ),
    file=FileOutputConfig(
        enabled=True,
        level=LogLevel.DEBUG,         # Уровень для файлов
        format=LogFormat.JSONL,       # JSONL или JSON
        base_dir=Path("logs"),
        max_file_size_mb=100,
        backup_count=10,
    )
)

configure_logging(config)
```

### Уровни логирования

| Уровень | Значение | Описание |
|---------|----------|----------|
| `LogLevel.DEBUG` | 10 | Отладочная информация |
| `LogLevel.INFO` | 20 | Информационные сообщения |
| `LogLevel.WARNING` | 30 | Предупреждения |
| `LogLevel.ERROR` | 40 | Ошибки |
| `LogLevel.CRITICAL` | 50 | Критические ошибки |

### Форматы вывода

**Для терминала:**
- `LogFormat.COLORED` - с цветами и иконками (рекомендуется)
- `LogFormat.SIMPLE` - `[INFO] сообщение`
- `LogFormat.DETAILED` - `[2024-01-01 12:00:00] [INFO] [component] сообщение`

**Для файлов:**
- `LogFormat.JSONL` - JSON Lines (одна запись на строку, рекомендуется)
- `LogFormat.JSON` - Pretty-print JSON

## API EventBusLogger

### Основные методы

```python
# Асинхронные
await logger.info("Сообщение")
await logger.info("Форматирование: %s, %d", "строка", 42)
await logger.debug("Отладка", extra={"key": "value"})
await logger.warning("Предупреждение")
await logger.error("Ошибка")
await logger.exception("Ошибка с исключением", exc=e)

# Синхронные (для вызова без await)
logger.info_sync("Сообщение")
logger.debug_sync("Отладка")
logger.warning_sync("Предупреждение")
logger.error_sync("Ошибка")
```

### Специализированные методы

```python
# LLM промпты и ответы
await logger.log_llm_prompt(
    component="LLMProvider",
    phase="generation",
    system_prompt="...",
    user_prompt="..."
)

await logger.log_llm_response(
    component="LLMProvider",
    phase="generation",
    response="...",
    tokens=150,
    latency_ms=234.5
)

# Сессии
await logger.start_session(goal="Достичь цели")
await logger.end_session(success=True, result="Успешно")
```

## Обработчики

### TerminalLogHandler

Подписывается на события логирования и выводит в терминал:

```python
from core.infrastructure.logging import TerminalLogHandler, setup_logging

# Автоматическая настройка при инициализации
terminal_handler, file_handler = setup_logging(event_bus)

# Ручное управление
terminal_handler.enable()   # Включить вывод
terminal_handler.disable()  # Выключить вывод
terminal_handler.unsubscribe()  # Отписаться от событий
```

### FileLogHandler

Записывает логи в файлы с ротацией:

```python
from core.infrastructure.logging import FileLogHandler

# Автоматическое создание файлов
# logs/common/common.log - общие логи
# logs/sessions/{session_id}/session.log - логи сессии

# Закрытие файлов при завершении
file_handler.close()
```

## Структура файлов логов

```
logs/
├── common/
│   └── 2024-01-01_common.log    # Общие логи
├── sessions/
│   ├── session_123/
│   │   └── 2024-01-01_session.log  # Логи конкретной сессии
│   └── session_456/
│       └── 2024-01-01_session.log
└── by_date/
    └── 2024-01-01.log            # Логи по датам
```

## Миграция со старой системы

### Старый код
```python
from core.infrastructure.logging.event_bus_log_handler import EventBusLogger
logger = EventBusLogger(event_bus, source="MyComponent")
await logger.info("Сообщение")
```

### Новый код
```python
from core.infrastructure.logging import EventBusLogger
logger = EventBusLogger(event_bus, "system", "system", component="MyComponent")
await logger.info("Сообщение")
```

### Если нужен session_id и agent_id
```python
logger = EventBusLogger(
    event_bus, 
    session_id="session_123", 
    agent_id="agent_001", 
    component="MyComponent"
)
```

## Отладка

### Включение DEBUG режима

```python
from core.infrastructure.logging import enable_debug_mode

enable_debug_mode()  # DEBUG в терминал + файлы
```

### Изменение уровня логирования

```python
from core.infrastructure.logging import set_terminal_level, set_file_level, LogLevel

set_terminal_level(LogLevel.DEBUG)  # Только терминал
set_file_level(LogLevel.DEBUG)      # Только файлы
```

## Рекомендации

1. **Используйте компонент как source** - это поможет фильтровать логи
2. **Не логируйте чувствительные данные** - токены, пароли, ключи
3. **Используйте exception() для ошибок** - автоматически добавляет тип исключения
4. **Настройте фильтры для отладки** - включайте только нужные компоненты
5. **Ротируйте файлы** - настройте `max_file_size_mb` и `backup_count`
