"""
Services - общие сервисы для behavior паттернов.

Содержит:
- fallback_strategy: стратегии обработки ошибок
"""
from .fallback_strategy import FallbackStrategyService

__all__ = [
    "FallbackStrategyService",
]
