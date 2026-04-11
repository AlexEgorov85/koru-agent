"""
Unified Logging System.

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────────┐
│                     Компоненты приложения                       │
│  (используют standard logging с LogEventType)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  LoggingSession │  ← session.py (ЕДИНЫЙ API)
                    │  (файловое)     │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Telemetry      │  ← core.infrastructure.telemetry
                    │  (обработчики)  │
                    └─────────────────┘

ВАЖНО:
- Terminal: онлайн вывод для разработчика (через EventTypeFilter)
- Session: структура по сессиям с LLM и метриками
- Metrics: сбор метрик через EventBus

КОНФИГУРАЦИЯ:
- core.config.logging_config.LoggingConfig — ЕДИНАЯ конфигурация
- core.config.paths.log_paths — централизованные пути

ЭКСПОРТ:
- LoggingSession: сессионное логирование
- LoggingConfig: конфигурация (из core.config.logging_config)
"""
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
