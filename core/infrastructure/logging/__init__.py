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
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TerminalHandler │  │  SessionHandler │  │  LogCollector   │
│ (терминал)      │  │  (сессия)       │  │  (метрики)      │
│                 │  │                 │  │                 │
│ - онлайн вывод  │  │ - session.log   │  │ - для обучения  │
│ - с иконками    │  │ - llm.jsonl     │  │                 │
│ - для разраба   │  │ - metrics.jsonl │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘

ВАЖНО:
- Terminal: онлайн вывод для разработчика (ВКЛЮЧЁН)
- Session: структура по сессиям с LLM и метриками (ВКЛЮЧЁН)

КОНФИГУРАЦИЯ:
- core.config.logging_config.LoggingConfig — ЕДИНАЯ конфигурация
- core.config.paths.log_paths — централизованные пути

ЭКСПОРТ:
- EventBusLogger: универсальный логгер
- create_logger: фабрика логгеров
- TerminalLogHandler, SessionLogHandler: обработчики
- LoggingConfig: конфигурация (из core.config.logging_config)
- setup_logging, shutdown_logging: управление
"""
from core.infrastructure.logging.logger import (
    EventBusLogger,
    create_logger,
    init_logging_system,
    shutdown_logging_system,
    get_session_logger,
    get_global_logger,
)

from core.infrastructure.logging.handlers import (
    TerminalLogHandler,
    TerminalLogFormatter,
    LoggingToEventBusHandler,
    setup_logging,
    shutdown_logging,
)

from core.infrastructure.logging.session_log_handler import (
    SessionLogHandler,
    create_session_log_handler,
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

from core.infrastructure.logging.structured import (
    StructuredLoggerMixin,
    ContextualLoggerMixin,
    session_id_var,
    agent_id_var,
    step_number_var,
    correlation_id_var,
    log_context,
    LoggingHealthCheck,
    patch_event_bus_logger,
)

# ============================================================
# УСТАРЕВШИЕ ЭКСПОРТЫ (заглушки)
# ============================================================

# FileLogHandler и FileLogFormatter УДАЛЕНЫ - дублировали SessionLogHandler
# Для обратной совместимости экспортируем заглушки из handlers.py
from core.infrastructure.logging.handlers import FileLogHandler, FileLogFormatter

# FileOutputConfig — алиас на FileConfig для обратной совместимости
from core.config.logging_config import FileConfig as FileOutputConfig

__all__ = [
    # Logger
    'EventBusLogger',
    'create_logger',
    'init_logging_system',
    'shutdown_logging_system',
    'get_session_logger',
    'get_global_logger',

    # Handlers
    'TerminalLogHandler',
    'TerminalLogFormatter',
    'LoggingToEventBusHandler',
    'SessionLogHandler',
    'create_session_log_handler',
    'setup_logging',
    'shutdown_logging',

    # Config (из единой конфигурации)
    'LoggingConfig',
    'LogConfig',
    'ConsoleConfig',
    'FileConfig',
    'FileOutputConfig',  # Alias для обратной совместимости
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

    # Structured & Contextual
    'StructuredLoggerMixin',
    'ContextualLoggerMixin',
    'session_id_var',
    'agent_id_var',
    'step_number_var',
    'correlation_id_var',
    'log_context',
    'LoggingHealthCheck',
    'patch_event_bus_logger',

    # Устаревшие (заглушки)
    'FileLogHandler',      # Заглушка
    'FileLogFormatter',    # Заглушка
]
