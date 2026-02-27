"""
Модуль универсального логирования.

EXPORTS:
- LogConfig, LogLevel: конфигурация логирования
- configure_logging, get_log_config: управление конфигурацией
- log_execution: декоратор для автоматического логирования (из log_mixin)
- LogComponentMixin: миксин для добавления логирования в компоненты
- LogFormatter: единый форматер логов
"""
from core.infrastructure.logging.log_config import (
    LogConfig,
    LogLevel,
    configure_logging,
    get_log_config,
)
from core.infrastructure.logging.log_mixin import log_execution, LogComponentMixin
from core.infrastructure.logging.log_formatter import LogFormatter

__all__ = [
    # Конфигурация
    "LogConfig",
    "LogLevel",
    "configure_logging",
    "get_log_config",
    # Декоратор
    "log_execution",
    # Миксин
    "LogComponentMixin",
    # Форматтер
    "LogFormatter",
]
