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

# ============================================================
# УСТАРЕВШИЕ ЭКСПОРТЫ (для обратной совместимости)
# ============================================================

# FileLogHandler ОТКЛЮЧЁН - дублировал SessionLogHandler
# Для обратной совместимости экспортируем заглушку
class FileLogHandler:
    """Устаревший обработчик (удалён, дублировал SessionLogHandler)."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "FileLogHandler удалён. Используйте SessionLogHandler."
        )


class FileOutputConfig:
    """Устаревший класс (удалён). Используйте FileConfig."""
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError(
            "FileOutputConfig удалён. Используйте FileConfig из core.config.logging_config."
        )


def get_log_manager():
    """Устаревшая функция (удалена)."""
    return None


# Для полной обратной совместимости
FileOutputConfig = FileConfig

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
    'SessionLogHandler',
    'create_session_log_handler',
    'setup_logging',
    'shutdown_logging',

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

    # Устаревшие (для обратной совместимости)
    'FileLogHandler',      # Заглушка
    'FileOutputConfig',    # Alias на FileConfig
    'get_log_manager',     # Заглушка
]
