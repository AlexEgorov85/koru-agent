"""
Интерфейсы инфраструктуры.

DEPRECATED: Используйте core.interfaces вместо этого модуля.
Этот файл оставлен для обратной совместимости.
"""

# Перенаправляем импорты на новые интерфейсы
from core.interfaces import (
    DatabaseInterface,
    LLMInterface,
    VectorInterface,
    CacheInterface,
    EventBusInterface,
    PromptStorageInterface,
    ContractStorageInterface,
    MetricsStorageInterface,
    LogStorageInterface,
)

# Aliases для обратной совместимости
DatabasePort = DatabaseInterface
LLMPort = LLMInterface
VectorPort = VectorInterface
CachePort = CacheInterface
EventPort = EventBusInterface

__all__ = [
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
    "CacheInterface",
    "EventBusInterface",
    "PromptStorageInterface",
    "ContractStorageInterface",
    "MetricsStorageInterface",
    "LogStorageInterface",
    # Aliases
    "DatabasePort",
    "LLMPort",
    "VectorPort",
    "CachePort",
    "EventPort",
]
