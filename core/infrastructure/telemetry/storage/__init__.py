"""
Telemetry Storage.

ЭКСПОРТ:
- FileSystemMetricsStorage: хранилище метрик на файловой системе
"""
from core.infrastructure.telemetry.storage.metrics_storage import FileSystemMetricsStorage

__all__ = [
    'FileSystemMetricsStorage',
]
