"""
Unified Logging System.

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────────┐
│                     Компоненты приложения                       │
│  (используют EventBusLogger для публикации логов)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  EventBusLogger │  ← logger.py (ЕДИНЫЙ API)
                    │  (публикация)   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    EventBus     │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Telemetry      │  ← core.infrastructure.telemetry
                    │  (обработчики)  │
                    └─────────────────┘

ВАЖНО:
- Terminal: онлайн вывод для разработчика
- Session: структура по сессиям с LLM и метриками
- Metrics: сбор метрик через EventBus

КОНФИГУРАЦИЯ:
- core.config.logging_config.LoggingConfig — ЕДИНАЯ конфигурация
- core.config.paths.log_paths — централизованные пути

ЭКСПОРТ:
- EventBusLogger: универсальный логгер
- create_logger: фабрика логгеров
- LoggingConfig: конфигурация (из core.config.logging_config)
"""
from core.infrastructure.logging.logger import (
    EventBusLogger,
    create_logger,
    init_logging_system,
    shutdown_logging_system,
    get_session_logger,
    get_global_logger,
)

from core.infrastructure.logging.session import (
    LoggingSession,
)

from core.infrastructure.logging.handlers import (
    EventTypeFilter,
)

from core.infrastructure.logging.event_types import (
    LogEventType,
)

# ============================================================
# ИМПОРТЫ ИЗ ЕДИНОЙ КОНФИГУРАЦИИ
# ============================================================
from core.config.logging_config import (
    LoggingConfig,
    LogConfig,  # Alias
    ConsoleConfig,
    FileConfig,
    SessionConfig,
    RetentionConfig,
    IndexingConfig,
    SymlinksConfig,
    LogLevel,
    LogFormat,
    get_logging_config,
    get_log_config,  # Alias
    configure_logging,
    set_log_level,
    set_file_level,
    disable_logging,
    enable_logging,
)

from core.config.paths import (
    log_paths,
    get_log_paths,
    init_paths,
    create_all_directories,
)

__all__ = [
    # Logger
    'EventBusLogger',
    'create_logger',
    'init_logging_system',
    'shutdown_logging_system',
    'get_session_logger',
    'get_global_logger',

    # LoggingSession
    'LoggingSession',

    # Handlers
    'EventTypeFilter',

    # Event Types
    'LogEventType',

    # Config (из единой конфигурации)
    'LoggingConfig',
    'LogConfig',
    'ConsoleConfig',
    'FileConfig',
    'SessionConfig',
    'RetentionConfig',
    'IndexingConfig',
    'SymlinksConfig',
    'LogLevel',
    'LogFormat',
    'get_logging_config',
    'get_log_config',
    'configure_logging',
    'set_log_level',
    'set_file_level',
    'disable_logging',
    'enable_logging',

    # Paths
    'log_paths',
    'get_log_paths',
    'init_paths',
    'create_all_directories',
]
