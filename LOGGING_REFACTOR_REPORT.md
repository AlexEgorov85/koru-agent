# Отчет о рефакторинге системы логирования

## Дата: 2026-03-03

## Резюме

Проведен полный рефакторинг системы логирования для устранения дублирования кода и создания предсказуемой архитектуры с гибкими настройками вывода.

## Проблемы до рефакторинга

### 1. Дублирование кода (3 реализации!)

| Компонент | Статус | Проблема |
|-----------|--------|----------|
| `core/infrastructure/logging/event_bus_log_handler.py` | ✅ Активный | 22KB, EventBusLogger |
| `core/infrastructure/event_bus/unified_logger.py` | ✅ Активный | 8KB, дублирует EventBusLogger |
| `core/infrastructure/logging/log_formatter.py` | ⚠️ Legacy | 4KB, "для обратной совместимости" |

### 2. Разные сигнатуры классов

```python
# event_bus_log_handler.py
class EventBusLogger:
    def __init__(self, event_bus, source: str = "", ...):

# unified_logger.py
class EventBusLogger:
    def __init__(self, event_bus, session_id: str, agent_id: str, ...):
```

### 3. Запутанные импорты

- 15 файлов импортировали из `event_bus_log_handler`
- 12 файлов импортировали из `unified_logger`
- Непредсказуемое поведение при использовании

## Решение

### Новая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     Компоненты приложения                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  EventBusLogger │  ← logger.py (ЕДИНЫЙ API)
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

### Новая структура файлов

```
core/infrastructure/logging/
├── __init__.py          # Публичный API
├── config.py            # Конфигурация (NEW)
├── logger.py            # EventBusLogger (NEW)
├── handlers.py          # Обработчики (NEW)
├── log_config.py        # Конфигурация хранения (существ.)
├── log_search.py        # Поиск по логам (существ.)
└── log_indexer.py       # Индексация (существ.)
```

### Удаленные файлы

- ❌ `core/infrastructure/logging/event_bus_log_handler.py` (22KB)
- ❌ `core/infrastructure/event_bus/unified_logger.py` (8KB)
- ❌ `core/infrastructure/logging/log_formatter.py` (4KB)

**Итого удалено: 34KB дублирующегося кода**

## Новые возможности

### 1. Гибкая конфигурация терминала

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
        level=LogLevel.INFO,
        format=LogFormat.COLORED,  # COLORED, SIMPLE, DETAILED
        show_debug=False,
        show_source=True,
        show_session_info=False,
        # Фильтры
        include_components={"LLMProvider", "Agent"},
        exclude_components={"DebugTool"},
    ),
    file=FileOutputConfig(
        enabled=True,
        level=LogLevel.DEBUG,
        format=LogFormat.JSONL,
        max_file_size_mb=100,
        backup_count=10,
    )
)
```

### 2. Единый API для всех компонентов

```python
from core.infrastructure.logging import EventBusLogger

logger = EventBusLogger(
    event_bus,
    session_id="session_123",
    agent_id="agent_001",
    component="MyComponent"
)

# Асинхронные методы
await logger.info("Сообщение")
await logger.debug("Детали: %s", data)
await logger.warning("Предупреждение")
await logger.error("Ошибка")
await logger.exception("Ошибка", exc=e)

# Синхронные версии
logger.info_sync("Сообщение без await")
```

### 3. Автоматическая ротация файлов

```
logs/
├── common/
│   └── 2024-01-01_common.log
├── sessions/
│   └── session_123/
│       └── 2024-01-01_session.log
└── by_date/
    └── 2024-01-01.log
```

## Обновленные файлы (21 файл)

### Core infrastructure
- ✅ `core/infrastructure/logging/__init__.py`
- ✅ `core/infrastructure/logging/config.py` (NEW)
- ✅ `core/infrastructure/logging/logger.py` (NEW)
- ✅ `core/infrastructure/logging/handlers.py` (NEW)
- ✅ `core/infrastructure/context/lifecycle_manager.py`
- ✅ `core/infrastructure/context/infrastructure_context.py` — **автоматическая инициализация обработчиков**
- ✅ `core/infrastructure/collectors/base/base_collector.py`
- ✅ `core/infrastructure/providers/base_provider.py`
- ✅ `core/infrastructure/providers/database/base.py`
- ✅ `core/infrastructure/providers/database/postgres_provider.py`
- ✅ `core/infrastructure/providers/llm/llama_cpp_provider.py`

### Application
- ✅ `core/application/context/application_context.py`
- ✅ `core/application/agent/runtime.py`
- ✅ `core/application/agent/components/behavior_manager.py`
- ✅ `core/application/behaviors/react/pattern.py`
- ✅ `core/application/services/base_service.py`
- ✅ `core/application/tools/vector_books_tool.py`
- ✅ `core/application/tools/sql_tool.py`
- ✅ `core/application/tools/file_tool.py`
- ✅ `core/application/skills/planning/skill.py`
- ✅ `core/application/skills/final_answer/skill.py`
- ✅ `core/application/skills/data_analysis/skill.py`

### Storage
- ✅ `core/infrastructure/storage/prompt_storage.py`
- ✅ `core/infrastructure/storage/file_system_data_source.py`
- ✅ `core/infrastructure/storage/contract_storage.py`
- ✅ `core/infrastructure/storage/capability_registry.py`

### Components & Utils
- ✅ `core/components/base_component.py`
- ✅ `core/utils/lifecycle.py`

### Tests
- ✅ `tests/application/skills/test_skills_integration.py`

### Main
- ✅ `main.py`

## Миграция кода

### До

```python
from core.infrastructure.logging.event_bus_log_handler import EventBusLogger
logger = EventBusLogger(event_bus, source="MyComponent")
await logger.info("Сообщение")
```

### После

```python
from core.infrastructure.logging import EventBusLogger
logger = EventBusLogger(event_bus, "system", "system", component="MyComponent")
await logger.info("Сообщение")
```

## Тестирование

```bash
# Проверка импорта
python -c "from core.infrastructure.logging import EventBusLogger; print('OK')"

# Проверка экспортов
python -c "from core.infrastructure.logging import setup_logging, shutdown_logging; print('OK')"

# Проверка удаления старых файлов
python -c "from core.infrastructure.logging.event_bus_log_handler import EventBusLogger"
# Ожидается: ModuleNotFoundError
```

## Документация

Создан новый документ:
- 📄 `docs/logging/ARCHITECTURE.md` - полное руководство по новой системе

## Преимущества новой системы

| Характеристика | До | После |
|---------------|-----|-------|
| Файлов с логированием | 3 (дубли) | 3 (четкое разделение) |
| Классов EventBusLogger | 2 (разные API) | 1 (единый API) |
| Настройки терминала | ❌ Нет | ✅ Гибкие фильтры |
| Настройки файлов | ❌ Нет | ✅ Ротация, форматы |
| Предсказуемость | ❌ Низкая | ✅ Высокая |
| Поддержка | ❌ Сложная | ✅ Простая |

## Рекомендации

1. **Использовать `component` для идентификации** - помогает фильтровать логи
2. **Настраивать фильтры для отладки** - включать только нужные компоненты
3. **Не логировать чувствительные данные** - токены, пароли, ключи
4. **Использовать `exception()` для ошибок** - автоматически добавляет тип исключения
5. **Ротация файлов** - настроить `max_file_size_mb` и `backup_count`

## Заключение

Рефакторинг завершен успешно. Система логирования теперь:
- ✅ **Единая** - один класс EventBusLogger
- ✅ **Предсказуемая** - четкое разделение ответственности
- ✅ **Гибкая** - настройки терминала и файлов
- ✅ **Чистая** - удалено 34KB дублирующегося кода
