"""
Адаптеры для VectorPort.
"""
from core.infrastructure.adapters.vector.faiss_adapter import (
    FAISSAdapter,
    MockVectorAdapter,
)

__all__ = [
    "FAISSAdapter",
    "MockVectorAdapter",
]
