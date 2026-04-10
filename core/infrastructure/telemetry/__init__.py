"""
Telemetry Module — обработчики и хранилища телеметрии.

АРХИТЕКТУРА:
- SessionLogHandler: запись логов сессий в файлы
- FileSystemMetricsStorage: хранилище метрик
- MetricsPublisher: публикация метрик (из core.components.services)
- TerminalLogHandler: вывод в консоль (только иконки)

USAGE:
```python
from core.infrastructure.telemetry import SessionLogHandler, FileSystemMetricsStorage
```
"""
from core.infrastructure.telemetry.handlers import (
    TerminalLogHandler,
    TerminalLogFormatter,
    SessionLogHandler,
)

from core.infrastructure.telemetry.storage import (
    FileSystemMetricsStorage,
)

__all__ = [
    # Handlers
    'TerminalLogHandler',
    'TerminalLogFormatter',
    'SessionLogHandler',

    # Storage
    'FileSystemMetricsStorage',
]
