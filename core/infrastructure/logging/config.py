"""
Конфигурация системы логирования.

FEATURES:
- Гибкие настройки вывода в терминал и файлы
- Уровни логирования для разных компонентов
- Форматы сообщений
- Политики ротации файлов
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Set
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(int, Enum):
    """Уровни логирования."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(str, Enum):
    """Форматы вывода логов."""
    SIMPLE = "simple"       # [INFO] message
    DETAILED = "detailed"   # [2024-01-01 12:00:00] [INFO] [component] message
    COLORED = "colored"     # С цветами и иконками (для терминала)
    JSON = "json"           # JSON формат (для файлов)
    JSONL = "jsonl"         # JSON Lines (для файлов)


@dataclass
class TerminalOutputConfig:
    """Настройки вывода в терминал."""
    enabled: bool = True
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.COLORED
    show_debug: bool = False
    show_source: bool = True
    show_timestamp: bool = False
    show_session_info: bool = False
    # Фильтры по компонентам
    include_components: Set[str] = field(default_factory=set)  # Если пусто - все
    exclude_components: Set[str] = field(default_factory=set)
    # Фильтры по уровням событий
    include_event_types: Set[str] = field(default_factory=set)
    exclude_event_types: Set[str] = field(default_factory=set)


@dataclass
class FileOutputConfig:
    """Настройки вывода в файлы."""
    enabled: bool = True
    level: LogLevel = LogLevel.DEBUG
    format: LogFormat = LogFormat.JSONL
    base_dir: Path = field(default_factory=lambda: Path("logs"))
    # Ротация файлов
    max_file_size_mb: int = 100
    backup_count: int = 10
    # Структура директорий
    organize_by_session: bool = True
    organize_by_date: bool = True
    # Имена файлов
    session_log_name: str = "session.log"
    common_log_name: str = "common.log"


@dataclass
class LoggingConfig:
    """
    Общая конфигурация системы логирования.

    ATTRIBUTES:
    - terminal: Настройки вывода в терминал
    - file: Настройки вывода в файлы
    - default_session_id: ID сессии по умолчанию
    - default_agent_id: ID агента по умолчанию
    """
    terminal: TerminalOutputConfig = field(default_factory=TerminalOutputConfig)
    file: FileOutputConfig = field(default_factory=FileOutputConfig)
    
    default_session_id: str = "system"
    default_agent_id: str = "system"
    
    @property
    def logs_dir(self) -> Path:
        """Базовая директория для логов."""
        return self.file.base_dir
    
    @property
    def sessions_dir(self) -> Path:
        """Директория для логов по сессиям."""
        return self.logs_dir / "sessions"
    
    @property
    def common_dir(self) -> Path:
        """Директория для общих логов."""
        return self.logs_dir / "common"


# Глобальный экземпляр конфигурации
_global_config: Optional[LoggingConfig] = None


def get_logging_config() -> LoggingConfig:
    """Получение конфигурации логирования."""
    global _global_config
    if _global_config is None:
        _global_config = LoggingConfig()
    return _global_config


def configure_logging(config: LoggingConfig) -> None:
    """
    Настройка конфигурации логирования.

    ARGS:
        config: Новая конфигурация
    """
    global _global_config
    _global_config = config


def set_terminal_level(level: LogLevel) -> None:
    """Установка уровня логирования для терминала."""
    config = get_logging_config()
    config.terminal.level = level


def set_file_level(level: LogLevel) -> None:
    """Установка уровня логирования для файлов."""
    config = get_logging_config()
    config.file.level = level


def enable_debug_mode() -> None:
    """Включение режима отладки (DEBUG в терминал + файлы)."""
    config = get_logging_config()
    config.terminal.level = LogLevel.DEBUG
    config.terminal.show_debug = True
    config.file.level = LogLevel.DEBUG


# Alias для обратной совместимости
LogConfig = LoggingConfig
get_log_config = get_logging_config
