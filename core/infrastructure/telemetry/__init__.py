"""
Telemetry Module — единая точка сбора телеметрии.

АРХИТЕКТУРА:
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

USAGE:
```python
from core.infrastructure.telemetry import init_telemetry

telemetry = await init_telemetry(event_bus)
```

КОМПОНЕНТЫ:
- TelemetryCollector: единый сборщик
- TerminalLogHandler: вывод в консоль (только иконки)
- SessionLogHandler: запись в файлы сессий
- FileSystemMetricsStorage: хранилище метрик
"""
from core.infrastructure.telemetry.telemetry_collector import (
    TelemetryCollector,
    get_telemetry,
    init_telemetry,
    shutdown_telemetry,
)

from core.infrastructure.telemetry.handlers import (
    TerminalLogHandler,
    TerminalLogFormatter,
    SessionLogHandler,
)

from core.infrastructure.telemetry.storage import (
    FileSystemMetricsStorage,
)

__all__ = [
    # Main
    'TelemetryCollector',
    'get_telemetry',
    'init_telemetry',
    'shutdown_telemetry',

    # Handlers
    'TerminalLogHandler',
    'TerminalLogFormatter',
    'SessionLogHandler',

    # Storage
    'FileSystemMetricsStorage',
]
