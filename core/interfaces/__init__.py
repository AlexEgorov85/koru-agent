"""
Интерфейсы инфраструктуры.

Эти интерфейсы определяют контракты для всех реализаций.
Используйте их для типизации и зависимости.
"""

from core.interfaces.cache import CacheInterface
from core.interfaces.database import DatabaseInterface
from core.interfaces.llm import LLMInterface
from core.interfaces.vector import VectorInterface
from core.interfaces.event_bus import EventBusInterface
from core.interfaces.prompt_storage import PromptStorageInterface
from core.interfaces.contract_storage import ContractStorageInterface
from core.interfaces.metrics_storage import MetricsStorageInterface
from core.interfaces.log_storage import LogStorageInterface

__all__ = [
    "CacheInterface",
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
    "EventBusInterface",
    "PromptStorageInterface",
    "ContractStorageInterface",
    "MetricsStorageInterface",
    "LogStorageInterface",
]
