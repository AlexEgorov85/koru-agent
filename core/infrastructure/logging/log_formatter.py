"""
LogFormatter - для обратной совместимости.

NOTE: В новой системе используется LogManager для логирования.
Этот модуль оставлен для совместимости со старым кодом.
"""
import logging
import logging.handlers
import os
from typing import Optional, Dict


class LogFormatter(logging.Formatter):
    """
    Форматер логов для обратной совместимости.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'
    
    def __init__(self, format_type: str = "text", use_colors: bool = True):
        super().__init__()
        self.format_type = format_type
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирование записи лога."""
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        
        if self.use_colors and level in self.COLORS:
            level = f"{self.COLORS[level]}{level}{self.RESET}"
        
        message = record.getMessage()
        return f"{timestamp} | {level:8} | {record.name} | {message}"


def setup_logging(
    level: int = logging.INFO,
    format_type: str = "text",
    log_file: Optional[str] = None,
    log_file_max_size: int = 10485760,
    log_file_backup_count: int = 5,
    use_colors: bool = True,
    module_levels: Optional[Dict[str, int]] = None
) -> logging.Logger:
    """
    Настройка базового логирования для приложения.
    
    ARGS:
        level: уровень логирования
        format_type: тип формата ("text" или "json")
        log_file: путь к файлу логов (опционально)
        log_file_max_size: максимальный размер файла лога в байтах
        log_file_backup_count: количество резервных файлов лога
        use_colors: использовать цвета для консольного вывода
        module_levels: словарь с уровнями логирования для конкретных модулей
        
    RETURNS:
        настроенный корневой логгер
    """
    formatter = LogFormatter(format_type=format_type, use_colors=use_colors)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Файловый обработчик с ротацией (если указан)
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_file_max_size,
            backupCount=log_file_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(LogFormatter(format_type="text", use_colors=False))
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
    else:
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(console_handler)
    
    # Применение уровней для конкретных модулей
    if module_levels:
        for module_name, module_level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(module_level)
            module_logger.propagate = False
    
    return root_logger
