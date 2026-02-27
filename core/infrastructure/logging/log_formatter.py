"""
Единый форматер для логов.

USAGE:
    from core.infrastructure.logging.log_formatter import LogFormatter
    import logging

    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter())
    logger.addHandler(handler)
"""
import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any


class LogFormatter(logging.Formatter):
    """
    Единый форматер для логов.
    
    FEATURES:
    - Поддержка структурированного формата (JSON)
    - Цветной вывод для консоли
    - Добавление временных меток в ISO формате
    - Поддержка дополнительных полей
    
    EXAMPLE:
        formatter = LogFormatter(
            format_type="json",  # или "text"
            include_timestamp=True,
            include_level=True,
            include_logger_name=True
        )
    """
    
    # ANSI цвета для уровней логирования
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(
        self,
        format_type: str = "text",
        include_timestamp: bool = True,
        include_level: bool = True,
        include_logger_name: bool = True,
        include_extra_fields: bool = True,
        use_colors: bool = True
    ):
        """
        Инициализация форматера.
        
        ARGS:
            format_type: тип формата ("text" или "json")
            include_timestamp: включать временную метку
            include_level: включать уровень логирования
            include_logger_name: включать имя логгера
            include_extra_fields: включать дополнительные поля
            use_colors: использовать цвета для консольного вывода
        """
        super().__init__()
        self.format_type = format_type
        self.include_timestamp = include_timestamp
        self.include_level = include_level
        self.include_logger_name = include_logger_name
        self.include_extra_fields = include_extra_fields
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирование записи лога.
        
        ARGS:
            record: запись лога
        
        RETURNS:
            отформатированная строка
        """
        if self.format_type == "json":
            return self._format_json(record)
        else:
            return self._format_text(record)
    
    def _format_text(self, record: logging.LogRecord) -> str:
        """
        Текстовое форматирование записи лога.
        
        ARGS:
            record: запись лога
        
        RETURNS:
            отформатированная строка
        """
        parts = []
        
        # Временная метка
        if self.include_timestamp:
            timestamp = datetime.fromtimestamp(record.created).isoformat()
            parts.append(timestamp)
        
        # Имя логгера
        if self.include_logger_name:
            parts.append(record.name)
        
        # Уровень логирования (с цветом если нужно)
        if self.include_level:
            level = record.levelname
            if self.use_colors and level in self.COLORS:
                level = f"{self.COLORS[level]}{level}{self.RESET}"
            parts.append(level)
        
        # Сообщение
        message = record.getMessage()
        parts.append(message)
        
        # Добавление stack trace если есть
        if record.exc_info:
            message_with_exception = self.formatException(record.exc_info)
            parts.append(message_with_exception)
        
        # Дополнительные поля
        if self.include_extra_fields:
            extra_fields = self._get_extra_fields(record)
            if extra_fields:
                extra_str = " | ".join(f"{k}={v}" for k, v in extra_fields.items())
                parts.append(extra_str)
        
        return " | ".join(parts)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """
        JSON форматирование записи лога.
        
        ARGS:
            record: запись лога
        
        RETURNS:
            JSON строка
        """
        log_data: Dict[str, Any] = {}
        
        # Временная метка
        if self.include_timestamp:
            log_data['timestamp'] = datetime.fromtimestamp(record.created).isoformat()
        
        # Уровень логирования
        if self.include_level:
            log_data['level'] = record.levelname
        
        # Имя логгера
        if self.include_logger_name:
            log_data['logger'] = record.name
        
        # Сообщение
        log_data['message'] = record.getMessage()
        
        # Дополнительные поля
        if self.include_extra_fields:
            extra_fields = self._get_extra_fields(record)
            if extra_fields:
                log_data['extra'] = extra_fields
        
        # Информация об исключении
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)
    
    def _get_extra_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Получение дополнительных полей из записи лога.
        
        ARGS:
            record: запись лога
        
        RETURNS:
            словарь с дополнительными полями
        """
        skip_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'message', 'asctime'
        }
        
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in skip_fields:
                extra_fields[key] = value
        
        return extra_fields


def setup_logging(
    level: int = logging.INFO,
    format_type: str = "text",
    log_file: Optional[str] = None,
    log_file_max_size: int = 10485760,  # 10MB
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
        log_file_max_size: максимальный размер файла лога в байтах (по умолчанию 10MB)
        log_file_backup_count: количество резервных файлов лога (по умолчанию 5)
        use_colors: использовать цвета для консольного вывода
        module_levels: словарь с уровнями логирования для конкретных модулей

    RETURNS:
        настроенный корневой логгер
    """
    # Создание форматера
    formatter = LogFormatter(
        format_type=format_type,
        use_colors=use_colors
    )

    # Консольный обработчик - ТОЛЬКО WARNING и выше
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    # Файловый обработчик с ротацией (если указан)
    if log_file:
        # Создание директории для логов если не существует
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # RotatingFileHandler для ротации логов
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_file_max_size,
            backupCount=log_file_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(LogFormatter(format_type="text", use_colors=False))
        
        # Настройка корневого логгера
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
            # Отключаем распространение в корневой логгер
            module_logger.propagate = False
    
    return root_logger
