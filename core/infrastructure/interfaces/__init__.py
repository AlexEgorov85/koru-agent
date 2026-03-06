"""
Интерфейсы инфраструктуры.

DEPRECATED: Используйте core.interfaces вместо этого модуля.
"""

from core.interfaces import (
    CacheInterface,
    DatabaseInterface,
    LLMInterface,
    VectorInterface,
)

__all__ = [
    "CacheInterface",
    "DatabaseInterface",
    "LLMInterface",
    "VectorInterface",
]
