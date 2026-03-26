# 📊 Telemetry Module

Единая точка сбора телеметрии для Agent_v5.

## 🎯 Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    TelemetryCollector                       │
│  (подписка на события EventBus)                             │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TerminalHandler │  │ SessionHandler  │  │ MetricsHandler  │
│ (консоль)       │  │ (файлы сессий)  │  │ (метрики)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## 📦 Компоненты

### TelemetryCollector

Единый сборщик телеметрии. Подписывается на события EventBus и маршрутизирует их обработчикам.

**Ответственность:**
- Подписка на события (SKILL_EXECUTED, ERROR_OCCURRED, и т.д.)
- Сбор метрик через MetricsPublisher
- Управление обработчиками

### TerminalLogHandler

Вывод логов в консоль с умным форматированием.

**Особенности:**
- Иконки для разных типов событий (🧠 этап, 🔧 инструмент, ❌ ошибка)
- Фильтрация шума
- Показывает только meaningful execution trace

### SessionLogHandler

Запись всех событий сессии в один файл.

**Структура:**
```
logs/sessions/
└── 2026-03-26_14-30-00/
    └── session.jsonl  ← ВСЕ события в одном файле
```

### LoggingToEventBusHandler

Перехват стандартного logging module и направление в EventBus.

**Игнорируемые логгеры:**
- `core.infrastructure.event_bus.*`
- `core.infrastructure.telemetry.*`

### FileSystemMetricsStorage

Хранилище метрик на файловой системе.

**Структура:**
```
data/metrics/
└── {capability}/
    └── {version}/
        ├── metrics_2026-03-26.json
        └── aggregated.json
```

## 🚀 Использование

### Базовое

```python
from core.infrastructure.telemetry import init_telemetry

# Инициализация
telemetry = await init_telemetry(
    event_bus=event_bus,
    storage_dir=Path('data'),
    log_dir=Path('logs')
)

# Завершение
await shutdown_telemetry()
```

### С настройками

```python
from core.infrastructure.telemetry import TelemetryCollector

telemetry = TelemetryCollector(
    event_bus=event_bus,
    storage_dir=Path('data'),
    log_dir=Path('logs'),
    enable_terminal=True,      # Вывод в консоль
    enable_session_logs=True,  # Запись сессий
    enable_metrics=True        # Сбор метрик
)

await telemetry.initialize()
```

### Доступ к компонентам

```python
# Получение глобального экземпляра
telemetry = get_telemetry()

# Доступ к обработчикам
terminal = telemetry.get_terminal_handler()
session = telemetry.get_session_handler()
metrics = telemetry.get_metrics_publisher()
```

## 📊 События

TelemetryCollector подписывается на следующие события:

| Событие | Обработчик | Описание |
|---------|------------|----------|
| `SKILL_EXECUTED` | Metrics | Метрики выполнения (success, time, tokens) |
| `CAPABILITY_SELECTED` | Metrics | Счётчик выбора способности |
| `ERROR_OCCURRED` | Metrics | Метрики ошибок |
| `SESSION_STARTED` | Session, Metrics | Начало сессии |
| `SESSION_COMPLETED` | Session, Metrics | Завершение сессии |
| `LOG_*` | Terminal, Session | Логи приложения |
| `LLM_*` | Session | LLM события |

## 📁 Структура модуля

```
telemetry/
├── __init__.py                 # Экспорты
├── telemetry_collector.py      # Единый сборщик
├── handlers/
│   ├── __init__.py
│   ├── terminal_handler.py     # Вывод в консоль
│   ├── session_handler.py      # Запись в файлы
│   └── event_bridge_handler.py # logging → EventBus
└── storage/
    ├── __init__.py
    └── metrics_storage.py      # Хранилище метрик
```

## 🔄 Миграция

### Было (старая архитектура)

```python
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.logging import SessionLogHandler, TerminalLogHandler

metrics = MetricsCollector(event_bus, storage)
session = SessionLogHandler(event_bus)
```

### Стало (новая архитектура)

```python
from core.infrastructure.telemetry import init_telemetry

telemetry = await init_telemetry(event_bus)
```

## ⚙️ Конфигурация

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `event_bus` | UnifiedEventBus | - | Шина событий |
| `storage_dir` | Path | 'data' | Директория для данных |
| `log_dir` | Path | 'logs' | Директория для логов |
| `enable_terminal` | bool | True | Вывод в консоль |
| `enable_session_logs` | bool | True | Запись сессий |
| `enable_metrics` | bool | True | Сбор метрик |

## 🧪 Тестирование

```bash
pytest tests/infrastructure/test_telemetry.py -v
```
