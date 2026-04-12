"""
Единая конфигурация системы логирования.

ЦЕНТРАЛИЗУЕТ:
- Настройки уровня логирования
- Форматы вывода (text/json/jsonl)
- Политики ротации файлов
- Настройки сессионного логирования

ИСПОЛЬЗОВАНИЕ:
```python
from core.config.logging_config import LoggingConfig, get_logging_config

config = get_logging_config()
```
"""
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict
from enum import Enum
import logging


# ============================================================
# Перечисления
# ============================================================

class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    @classmethod
    def from_logging_level(cls, level: int) -> str:
        """Конвертация из logging.* в строку."""
        mapping = {
            logging.DEBUG: cls.DEBUG.value,
            logging.INFO: cls.INFO.value,
            logging.WARNING: cls.WARNING.value,
            logging.ERROR: cls.ERROR.value,
            logging.CRITICAL: cls.CRITICAL.value,
        }
        return mapping.get(level, cls.INFO.value)
    
    @classmethod
    def to_logging_level(cls, level: str) -> int:
        """Конвертация из строки в logging.*"""
        mapping = {
            cls.DEBUG.value: logging.DEBUG,
            cls.INFO.value: logging.INFO,
            cls.WARNING.value: logging.WARNING,
            cls.ERROR.value: logging.ERROR,
            cls.CRITICAL.value: logging.CRITICAL,
        }
        return mapping.get(level, logging.INFO)


class LogFormat(str, Enum):
    """Форматы вывода логов."""
    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"


# ============================================================
# Конфигурации подсистем
# ============================================================

class ConsoleConfig(BaseModel):
    """Настройки консольного вывода."""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Включить консольный вывод")
    level: str = Field(default="INFO", description="Уровень логирования")
    format: LogFormat = Field(default=LogFormat.TEXT, description="Формат вывода")
    use_colors: bool = Field(default=True, description="Использовать цвета")
    use_icons: bool = Field(default=True, description="Использовать иконки")
    allowed_terminal_events: Optional[set] = Field(
        default_factory=lambda: _default_allowed_events(),
        description="Разрешённые LogEventType для консоли (None = все)"
    )


def _default_allowed_events():
    """Дефолные события для терминала (ленивый импорт для избежания циклических импортов)."""
    from core.infrastructure.logging.event_types import LogEventType
    return {
        LogEventType.USER_PROGRESS,
        LogEventType.USER_RESULT,
        LogEventType.USER_MESSAGE,
        LogEventType.USER_QUESTION,
        LogEventType.AGENT_START,
        LogEventType.AGENT_STOP,
        LogEventType.TOOL_CALL,
        LogEventType.TOOL_RESULT,
        LogEventType.TOOL_ERROR,
        LogEventType.LLM_CALL,
        LogEventType.LLM_RESPONSE,
        LogEventType.LLM_ERROR,
        LogEventType.DB_QUERY,
        LogEventType.DB_RESULT,
        LogEventType.DB_ERROR,
        LogEventType.WARNING,
        LogEventType.ERROR,
        LogEventType.CRITICAL,
    }


class FileConfig(BaseModel):
    """Настройки файлового вывода."""
    model_config = ConfigDict(validate_assignment=True)
    
    enabled: bool = Field(default=True, description="Включить файловый вывод")
    level: str = Field(default="DEBUG", description="Уровень логирования")
    format: LogFormat = Field(default=LogFormat.JSONL, description="Формат вывода")
    
    # Ротация
    max_file_size_mb: int = Field(default=100, ge=1, description="Макс. размер файла (MB)")
    backup_count: int = Field(default=10, ge=0, description="Кол-во резервных файлов")
    
    # Структура
    organize_by_session: bool = Field(default=True, description="Организовать по сессиям")
    organize_by_date: bool = Field(default=True, description="Организовать по датам")


class SessionConfig(BaseModel):
    """Настройки сессионного логирования."""
    model_config = ConfigDict(validate_assignment=True)
    
    enabled: bool = Field(default=True, description="Включить сессионное логирование")
    format: LogFormat = Field(default=LogFormat.JSONL, description="Формат логов сессии")
    llm_format: LogFormat = Field(default=LogFormat.JSONL, description="Формат LLM логов")
    metrics_format: LogFormat = Field(default=LogFormat.JSONL, description="Формат метрик")
    
    # Хранение
    retention_days: int = Field(default=30, ge=1, description="Срок хранения сессий (дней)")
    archive_enabled: bool = Field(default=True, description="Включить архивирование")


class RetentionConfig(BaseModel):
    """Политика хранения логов."""
    model_config = ConfigDict(validate_assignment=True)
    
    active_days: int = Field(default=7, ge=1, description="Срок хранения активных логов")
    archive_months: int = Field(default=12, ge=1, description="Срок хранения архива")
    max_size_mb: int = Field(default=100, ge=1, description="Макс. размер файла")
    max_files_per_day: int = Field(default=100, ge=1, description="Макс. файлов в день")


class IndexingConfig(BaseModel):
    """Настройки индексации логов."""
    model_config = ConfigDict(validate_assignment=True)
    
    enabled: bool = Field(default=True, description="Включить индексацию")
    index_sessions: bool = Field(default=True, description="Индексировать сессии")
    index_agents: bool = Field(default=True, description="Индексировать агентов")
    update_interval_sec: int = Field(default=60, ge=1, description="Интервал обновления")


class SymlinksConfig(BaseModel):
    """Настройки symlink."""
    model_config = ConfigDict(validate_assignment=True)
    
    enabled: bool = Field(default=True, description="Включить symlink")
    latest_session: bool = Field(default=True, description="Symlink на последнюю сессию")
    latest_agent: bool = Field(default=True, description="Symlink на последнего агента")
    latest_llm: bool = Field(default=True, description="Symlink на последние LLM логи")


# ============================================================
# Основная конфигурация
# ============================================================

class LoggingConfig(BaseModel):
    """
    ЕДИНАЯ конфигурация системы логирования.
    
    ОБЪЕДИНЯЕТ:
    - LoggingConfig из infrastructure/logging/config.py
    - LoggingConfig из infrastructure/logging/log_config.py
    - LoggingSettings из core/config/settings.py
    - LoggingConfig из core/config/app_config.py
    
    ATTRIBUTES:
    - enabled: Глобальное включение/выключение логирования
    - level: Базовый уровень логирования
    - console: Настройки консольного вывода
    - file: Настройки файлового вывода
    - session: Настройки сессионного логирования
    - retention: Политика хранения
    - indexing: Настройки индексации
    - symlinks: Настройки symlink
    """
    model_config = ConfigDict(validate_assignment=True, extra='allow')
    
    # Глобальные настройки
    enabled: bool = Field(default=True, description="Глобальное включение логирования")
    level: str = Field(default="INFO", description="Базовый уровень логирования")
    
    # Подсистемы
    console: ConsoleConfig = Field(default_factory=ConsoleConfig, description="Консоль")
    file: FileConfig = Field(default_factory=FileConfig, description="Файлы")
    session: SessionConfig = Field(default_factory=SessionConfig, description="Сессии")
    
    # Хранение
    retention: RetentionConfig = Field(default_factory=RetentionConfig, description="Хранение")
    indexing: IndexingConfig = Field(default_factory=IndexingConfig, description="Индексация")
    symlinks: SymlinksConfig = Field(default_factory=SymlinksConfig, description="Symlinks")
    
    # Форматы (для обратной совместимости)
    format: LogFormat = Field(default=LogFormat.JSONL, description="Основной формат")
    agent_format: LogFormat = Field(default=LogFormat.TEXT, description="Формат логов агента")
    
    # Пути (будут переопределены через paths.py)
    base_dir: str = Field(default="logs", description="Базовая директория логов")
    
    @field_validator('level', mode='before')
    @classmethod
    def validate_level(cls, v):
        """Проверка уровня логирования."""
        # Поддержка Enum и строк
        if isinstance(v, LogLevel):
            return v.value
        if isinstance(v, str):
            v_upper = v.upper()
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v_upper not in valid_levels:
                raise ValueError(f"Level must be one of: {valid_levels}")
            return v_upper
        return v
    
    @property
    def logs_dir(self) -> Path:
        """Базовая директория для логов."""
        return Path(self.base_dir)
    
    @property
    def sessions_dir(self) -> Path:
        """Директория для логов по сессиям."""
        return self.logs_dir / "sessions"
    
    @property
    def archive_dir(self) -> Path:
        """Директория архива."""
        return self.logs_dir / "archive"
    
    @property
    def indexed_dir(self) -> Path:
        """Директория индексов."""
        return self.logs_dir / "indexed"
    
    @property
    def common_dir(self) -> Path:
        """Директория для общих логов."""
        return self.logs_dir / "common"
    
    def get_session_dir(self, session_id: str) -> Path:
        """Получить директорию сессии."""
        return self.sessions_dir / session_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """Создание из словаря."""
        return cls(**data)


# ============================================================
# Глобальный экземпляр и функции
# ============================================================

_global_config: Optional[LoggingConfig] = None


def get_logging_config() -> LoggingConfig:
    """
    Получить конфигурацию логирования.
    
    RETURNS:
    - LoggingConfig: конфигурация (создаёт новую если не инициализирована)
    """
    global _global_config
    if _global_config is None:
        _global_config = LoggingConfig()
    return _global_config


def configure_logging(config: LoggingConfig) -> None:
    """
    Настроить конфигурацию логирования.
    
    ARGS:
    - config: Новая конфигурация
    """
    global _global_config
    _global_config = config


def set_log_level(level: str) -> None:
    """
    Установить уровень логирования.
    
    ARGS:
    - level: Уровень (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    """
    config = get_logging_config()
    config.level = level
    config.console.level = level


def set_file_level(level: str) -> None:
    """
    Установить уровень логирования для файлов.
    
    ARGS:
    - level: Уровень (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    """
    config = get_logging_config()
    config.file.level = level


def disable_logging() -> None:
    """Отключить логирование."""
    config = get_logging_config()
    config.enabled = False
    config.console.enabled = False
    config.file.enabled = False
    config.session.enabled = False


def enable_logging() -> None:
    """Включить логирование."""
    config = get_logging_config()
    config.enabled = True
    config.console.enabled = True
    config.file.enabled = True
    config.session.enabled = True


# ============================================================
# Алиасы для обратной совместимости
# ============================================================

# Классы
LogConfig = LoggingConfig

# Функции
get_log_config = get_logging_config
configure = configure_logging

# Уровни логирования (для совместимости со старым кодом)
class LogLevelAlias:
    """Уровни логирования для обратной совместимости."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
