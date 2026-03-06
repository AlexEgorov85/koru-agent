"""
Порты (интерфейсы) для архитектуры Ports & Adapters.
"""
from core.infrastructure.interfaces.ports import (
    DatabasePort,
    LLMPort,
    VectorPort,
    CachePort,
    EventPort,
    StoragePort,
    MetricsPort,
)

__all__ = [
    "DatabasePort",
    "LLMPort",
    "VectorPort",
    "CachePort",
    "EventPort",
    "StoragePort",
    "MetricsPort",
]
