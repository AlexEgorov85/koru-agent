"""
Рекордеры для записи наблюдений агента.
"""
from core.agent.runtime.recorders.observation import (
    IObservationRecorder,
    DefaultObservationRecorder,
)

__all__ = [
    "IObservationRecorder",
    "DefaultObservationRecorder",
]
