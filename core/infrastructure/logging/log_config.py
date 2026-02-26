"""
Конфигурация универсального логирования.

USAGE:
    from core.infrastructure.logging.log_config import configure_logging, LogConfig, LogLevel
    
    configure_logging(LogConfig(
        level=LogLevel.DEBUG,
        log_parameters=True,
        log_result=False,  # Не логировать результаты (чувствительные данные)
        exclude_parameters=['password', 'api_key']
    ))
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogConfig:
    """
    Конфигурация логирования.
    
    ATTRIBUTES:
    - level: уровень логирования
    - format_string: формат строки лога
    - log_execution_start: логировать начало выполнения
    - log_execution_end: логировать завершение выполнения
    - log_parameters: логировать параметры методов
    - log_result: логировать результат выполнения
    - log_errors: логировать ошибки
    - log_duration: логировать время выполнения
    - exclude_parameters: список параметров для исключения (чувствительные данные)
    - max_parameter_length: максимальная длина логируемых параметров
    - max_result_length: максимальная длина логируемого результата
    - log_file: путь к файлу логов (опционально)
    - enable_event_bus: включить логирование в EventBus
    """
    # Уровень логирования
    level: LogLevel = LogLevel.INFO
    
    # Формат логов
    format_string: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    
    # Что логировать
    log_execution_start: bool = True
    log_execution_end: bool = True
    log_parameters: bool = True
    log_result: bool = True
    log_errors: bool = True
    log_duration: bool = True
    
    # Исключения из логирования (чувствительные данные)
    exclude_parameters: List[str] = field(default_factory=lambda: [
        'password', 'token', 'api_key', 'secret', 'credential'
    ])
    
    # Максимальная длина логируемых данных
    max_parameter_length: int = 1000
    max_result_length: int = 5000
    
    # Путь к файлу логов (опционально)
    log_file: Optional[str] = None
    
    # Включить логирование в EventBus
    enable_event_bus: bool = True


# Глобальная конфигурация
DEFAULT_LOG_CONFIG = LogConfig()


def get_log_config() -> LogConfig:
    """
    Получение текущей конфигурации логирования.
    
    RETURNS:
    - LogConfig: текущая конфигурация
    """
    return DEFAULT_LOG_CONFIG


def configure_logging(config: LogConfig) -> None:
    """
    Настройка конфигурации логирования.
    
    ARGS:
    - config: новая конфигурация логирования
    """
    global DEFAULT_LOG_CONFIG
    DEFAULT_LOG_CONFIG = config
