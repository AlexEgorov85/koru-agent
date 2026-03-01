"""
Unified Logging System через EventBus.

ЭКСПОРТИРУЕТ:
- EventBusLogger: универсальный логгер
- init_logging_system: инициализация
- shutdown_logging_system: завершение
- get_session_logger: получение логгера сессии
- create_logger: фабрика логгеров
"""
from core.infrastructure.event_bus.unified_logger import (
    EventBusLogger,
    init_logging_system,
    shutdown_logging_system,
    get_session_logger,
    create_logger,
)

# Для обратной совместимости
get_log_manager = lambda: None

__all__ = [
    'EventBusLogger',
    'init_logging_system',
    'shutdown_logging_system',
    'get_session_logger',
    'create_logger',
    'get_log_manager',
]
