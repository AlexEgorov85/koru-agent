"""
Модуль сервисов - содержит различные сервисы приложения.
"""

# NOTE: Avoiding circular imports - only import services that don't cause cycles

__all__ = [
    "MetricsPublisher",
    "MetricsContext",
    "record_metrics"
]