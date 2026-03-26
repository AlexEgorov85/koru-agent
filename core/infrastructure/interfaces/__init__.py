"""
Интерфейсы инфраструктуры.

Эти интерфейсы определяют контракты для всех реализаций.
Используйте их для типизации и зависимости.
"""

from core.infrastructure.interfaces.cache import CacheInterface
from core.infrastructure.interfaces.database import DatabaseInterface
from core.infrastructure.interfaces.llm import LLMInterface
from core.infrastructure.interfaces.vector import VectorInterface
from core.infrastructure.interfaces.event_bus import EventBusInterface

# Re-export из infrastructure.interfaces (объединённые)
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage, ILogStorage

# Aliases для обратной совместимости
MetricsStorageInterface = IMetricsStorage
LogStorageInterface = ILogStorage

__all__ = [
    "CacheInterface",
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
    "EventBusInterface",
    "IMetricsStorage",
    "ILogStorage",
    "MetricsStorageInterface",  # backward compatibility
    "LogStorageInterface",       # backward compatibility
]
