"""
Модуль стратегий - содержит интерфейсы и реализации для работы со стратегиями.
"""

from .i_strategy_storage import IStrategyStorage
from .strategy_storage import StrategyStorage

__all__ = [
    "IStrategyStorage",
    "StrategyStorage"
]