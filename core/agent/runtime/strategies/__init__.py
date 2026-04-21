"""
Стратегии завершения цикла выполнения агента.
"""
from core.agent.runtime.strategies.termination import (
    ITerminationStrategy,
    DefaultTerminationStrategy,
)

__all__ = [
    "ITerminationStrategy",
    "DefaultTerminationStrategy",
]
