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

__all__ = [
    "CacheInterface",
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
    "EventBusInterface",
]
