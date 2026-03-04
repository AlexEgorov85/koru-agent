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
│ TerminalHandler │  │  FileHandler    │  │ SessionHandler  │
│ (терминал)      │  │  (ОТКЛЮЧЁН!)    │  │ (сессия)        │
│                 │  │                 │  │                 │
│ - онлайн вывод  │  │ - дублировал    │  │ - common.log    │
│ - с цветами     │  │   SessionHandler│  │ - llm.jsonl     │
│ - для разраба   │  │                 │  │ - metrics.jsonl │
└─────────────────┘  └─────────────────┘  └─────────────────┘

ВАЖНО:
- Terminal: онлайн вывод для разработчика (ВКЛЮЧЁН)
- File: ОТКЛЮЧЁН (дублировал SessionHandler)
- Session: структура по сессиям с LLM и метриками (ВКЛЮЧЁН)

ЭКСПОРТ:
- EventBusLogger: универсальный логгер
- create_logger: фабрика логгеров
- TerminalLogHandler, FileLogHandler: обработчики
- LoggingConfig, TerminalOutputConfig, FileOutputConfig: конфигурация
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
    FileLogHandler,
    TerminalLogFormatter,
    FileLogFormatter,
    setup_logging,
    shutdown_logging,
)

from core.infrastructure.logging.config import (
    LoggingConfig,
    TerminalOutputConfig,
    FileOutputConfig,
    LogLevel,
    LogFormat,
    get_logging_config,
    configure_logging,
    set_terminal_level,
    set_file_level,
    enable_debug_mode,
)

from core.infrastructure.logging.session_log_handler import (
    SessionLogHandler,
    create_session_log_handler,
)

# Для обратной совместимости
LogConfig = LoggingConfig
get_log_config = get_logging_config
get_log_manager = lambda: None

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
    'FileLogHandler',
    'TerminalLogFormatter',
    'FileLogFormatter',
    'setup_logging',
    'shutdown_logging',
    
    # Config
    'LoggingConfig',
    'TerminalOutputConfig',
    'FileOutputConfig',
    'LogLevel',
    'LogFormat',
    'get_logging_config',
    'configure_logging',
    'set_terminal_level',
    'set_file_level',
    'enable_debug_mode',
    
    # Backward compatibility
    'LogConfig',
    'get_log_config',
    'get_log_manager',

    # Session logging
    'SessionLogHandler',
    'create_session_log_handler',
]
