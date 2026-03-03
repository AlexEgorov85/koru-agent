"""
Обработчики событий логирования.

КОМПОНЕНТЫ:
- TerminalLogHandler: вывод в терминал с форматированием
- FileLogHandler: запись в файлы с ротацией

АРХИТЕКТУРА:
- Подписываются на события LOG_* из EventBus
- Фильтруют сообщения согласно конфигурации
- Форматируют и выводят в целевое устройство
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus
from core.infrastructure.logging.config import (
    LoggingConfig,
    TerminalOutputConfig,
    FileOutputConfig,
    LogLevel,
    LogFormat,
    get_logging_config,
    configure_logging,
)


# =============================================================================
# TERMINAL HANDLER
# =============================================================================

class LoggingToEventBusHandler(logging.Handler):
    """
    Перехватывает стандартные logging записи и публикует их в EventBus.
    
    Это позволяет использовать новую систему логирования для ВСЕХ логов,
    включая те, что идут через logging.getLogger().info() и т.д.
    """
    
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setFormatter(logging.Formatter('%(message)s'))
    
    def emit(self, record: logging.LogRecord):
        """Публикация записи логирования в EventBus."""
        try:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            
            # Маппинг уровней logging на уровни EventBus
            level_map = {
                logging.DEBUG: "log.debug",
                logging.INFO: "log.info",
                logging.WARNING: "log.warning",
                logging.ERROR: "log.error",
                logging.CRITICAL: "log.error",
            }
            
            event_type_str = level_map.get(record.levelno, "log.info")
            event_type = {
                "log.debug": EventType.LOG_DEBUG,
                "log.info": EventType.LOG_INFO,
                "log.warning": EventType.LOG_WARNING,
                "log.error": EventType.LOG_ERROR,
            }.get(event_type_str, EventType.LOG_INFO)
            
            # Формируем данные события
            data = {
                "message": self.format(record),
                "level": record.levelname,
                "component": record.name,
                "logger_name": record.name,
            }
            
            # Публикуем событие (без await, через create_task)
            import asyncio
            asyncio.create_task(
                self.event_bus.publish(event_type, data=data, source=record.name)
            )
            
        except Exception:
            self.handleError(record)


class LogColors:
    """ANSI цвета для форматирования вывода в терминал."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Цвета по уровням
    INFO = "\033[36m"       # Cyan
    DEBUG = "\033[37m"      # White
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta
    SUCCESS = "\033[32m"    # Green

    # Цвета для компонентов
    LLM = "\033[34m"        # Blue
    REASONING = "\033[38;5;39m"   # Light blue
    DECISION = "\033[38;5;208m"   # Orange
    AGENT = "\033[38;5;27m"       # Dark blue
    CAPABILITY = "\033[38;5;148m" # Light green


class TerminalLogFormatter:
    """
    Форматировщик сообщений для терминала.

    Поддерживает несколько форматов:
    - SIMPLE: [INFO] message
    - DETAILED: [2024-01-01 12:00:00] [INFO] [component] message
    - COLORED: с цветами и иконками
    """

    # Иконки для типов событий
    TYPE_ICONS = {
        "log.info": "ℹ️",
        "log.debug": "🔹",
        "log.warning": "⚠️",
        "log.error": "❌",
        "llm.call.start": "🔄",
        "llm.call.progress": "⏳",
        "llm.call.success": "✅",
        "llm.call.retry": "🔁",
        "llm.call.timeout": "⏱️",
        "llm.call.error": "❌",
        "reasoning.start": "🧠",
        "reasoning.complete": "💡",
        "reasoning.error": "🔥",
        "context.analysis": "📊",
        "capability.register": "🔧",
        "decision.made": "🎯",
        "decision.validation": "✔️",
        "agent.start": "🤖",
        "agent.complete": "🏁",
        "agent.error": "💥",
        "session.start": "🚀",
        "session.complete": "✅",
        "session.failed": "❌",
    }

    TYPE_COLORS = {
        "llm.call.start": LogColors.LLM,
        "llm.call.progress": LogColors.LLM,
        "llm.call.success": LogColors.SUCCESS,
        "llm.call.retry": LogColors.WARNING,
        "llm.call.timeout": LogColors.ERROR,
        "llm.call.error": LogColors.ERROR,
        "reasoning.start": LogColors.REASONING,
        "reasoning.complete": LogColors.SUCCESS,
        "reasoning.error": LogColors.ERROR,
        "decision.made": LogColors.DECISION,
        "decision.validation": LogColors.DECISION,
        "capability.register": LogColors.CAPABILITY,
        "agent.start": LogColors.AGENT,
        "agent.complete": LogColors.SUCCESS,
        "agent.error": LogColors.ERROR,
        "session.start": LogColors.INFO,
        "session.complete": LogColors.SUCCESS,
        "session.failed": LogColors.ERROR,
    }
    
    def __init__(self, config: TerminalOutputConfig):
        self.config = config
        self._use_colors = config.format == LogFormat.COLORED
        self._message_count = 0
    
    def format(self, event: Event) -> Optional[str]:
        """
        Форматирование события для вывода в терминал.
        
        RETURNS:
            Отформатированная строка или None если сообщение не должно выводиться
        """
        data = event.data or {}
        message_type = data.get("type", event.event_type)
        level = data.get("level", "INFO")
        
        # Проверка фильтров
        if not self._should_log(event, message_type, level):
            return None
        
        # Форматирование в зависимости от типа
        if self.config.format == LogFormat.SIMPLE:
            return self._format_simple(event, data, level)
        elif self.config.format == LogFormat.DETAILED:
            return self._format_detailed(event, data, level)
        else:  # COLORED
            return self._format_colored(event, data, message_type, level)
    
    def _should_log(self, event: Event, message_type: str, level: str) -> bool:
        """Проверка фильтров конфигурации."""
        # Проверка уровня логирования
        level_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        msg_level = level_map.get(level.upper(), 20)  # По умолчанию INFO
        min_level = self.config.level.value  # LogLevel enum value (10, 20, 30, etc.)
        
        if msg_level < min_level:
            return False

        # Проверка show_debug
        if not self.config.show_debug and message_type == "log.debug":
            return False

        # Проверка фильтров компонентов
        component = event.data.get("component", "") if event.data else ""
        if self.config.include_components and component not in self.config.include_components:
            return False
        if self.config.exclude_components and component in self.config.exclude_components:
            return False

        # Проверка фильтров типов событий
        if self.config.include_event_types and message_type not in self.config.include_event_types:
            return False
        if self.config.exclude_event_types and message_type in self.config.exclude_event_types:
            return False

        return True
    
    def _format_simple(self, event: Event, data: Dict, level: str) -> str:
        """Простой формат: [INFO] message"""
        message = data.get("message", str(event.data)) if event.data else str(event)
        return f"[{level}] {message}"
    
    def _format_detailed(self, event: Event, data: Dict, level: str) -> str:
        """Детальный формат: [timestamp] [level] [component] message"""
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        message = data.get("message", str(event.data)) if event.data else str(event)
        component = data.get("component", event.source) if event.data else event.source
        
        parts = [f"[{timestamp}]", f"[{level}]"]
        if self.config.show_source and component:
            parts.append(f"[{component}]")
        parts.append(message)
        
        return " ".join(parts)
    
    def _format_colored(self, event: Event, data: Dict, message_type: str, level: str) -> str:
        """Цветной формат с иконками и структурой."""
        c = LogColors

        # Иконка и цвет
        icon = self.TYPE_ICONS.get(message_type, "•")
        color = self.TYPE_COLORS.get(message_type, self._get_level_color(level))

        message = data.get("message", str(event.data)) if event.data else str(event)
        component = data.get("component", "") if event.data else ""
        session_id = data.get("session_id", "") if event.data else ""
        agent_id = data.get("agent_id", "") if event.data else ""

        lines = []

        # Разделитель между сообщениями (не перед первым)
        if hasattr(self, '_message_count') and self._message_count > 0:
            lines.append(f"{c.DIM}{'─' * 70}{c.RESET}")
        else:
            self._message_count = 0

        # Заголовок с типом сообщения
        if self._use_colors:
            header = f"{color}{c.BOLD}[{icon} {message_type}]{c.RESET}"
        else:
            header = f"[{icon} {message_type}]"

        lines.append(header)
        
        # Основное сообщение с отступом
        lines.append(f"  {c.DIM}└─{c.RESET} {message}")

        # Контекст (session, agent, component)
        context_parts = []
        if self.config.show_session_info:
            if session_id and session_id != "system":
                context_parts.append(f"session={session_id[:8]}...")
            if agent_id and agent_id != "system":
                context_parts.append(f"agent={agent_id}")
        if self.config.show_source and component:
            context_parts.append(f"component={component}")

        if context_parts:
            lines.append(f"  {c.DIM}└─{c.RESET} {c.DIM}{' | '.join(context_parts)}{c.RESET}")

        # Дополнительные данные (ограничиваем количество)
        extra_data = {k: v for k, v in (data.items() if data else []) 
                     if k not in ["message", "level", "session_id", "agent_id", "component", "type"]}
        
        if extra_data and self.config.show_debug:
            for i, (key, value) in enumerate(extra_data.items()):
                str_value = str(value)
                if len(str_value) > 80:
                    str_value = str_value[:77] + "..."
                prefix = "   " if i == 0 else "  "
                lines.append(f"{prefix}{c.DIM}└─{c.RESET} {c.DIM}{key}:{c.RESET} {str_value}")

        self._message_count += 1
        return "\n".join(lines)
    
    def _get_level_color(self, level: str) -> str:
        """Получение цвета для уровня логирования."""
        level_colors = {
            "INFO": LogColors.INFO,
            "DEBUG": LogColors.DEBUG,
            "WARNING": LogColors.WARNING,
            "ERROR": LogColors.ERROR,
            "CRITICAL": LogColors.CRITICAL,
        }
        return level_colors.get(level.upper(), LogColors.RESET)


class TerminalLogHandler:
    """
    Обработчик вывода логов в терминал.
    
    ПОДПИСЫВАЕТСЯ НА:
    - LOG_INFO, LOG_DEBUG, LOG_WARNING, LOG_ERROR
    
    FEATURES:
    - Цветной вывод с иконками
    - Гибкие фильтры по компонентам и типам событий
    - Несколько форматов вывода
    """
    
    # Логгеры системы логирования (игнорируем чтобы избежать цикла)
    LOGGING_SYSTEM_LOGGERS = {"EventBusLog", "EventBus", "SessionWorker"}
    
    def __init__(self, event_bus: UnifiedEventBus, config: Optional[TerminalOutputConfig] = None):
        self.event_bus = event_bus
        self.config = config or get_logging_config().terminal
        self.formatter = TerminalLogFormatter(self.config)
        self.logger = logging.getLogger("EventBusLog")
        self.logger.propagate = False
        self._enabled = True
    
    def enable(self) -> None:
        """Включить вывод логов."""
        self._enabled = True
    
    def disable(self) -> None:
        """Выключить вывод логов."""
        self._enabled = False
    
    async def handle_log_event(self, event: Event) -> None:
        """Обработчик событий логирования."""
        if not self._enabled:
            return
        
        # Игнорируем события от логгеров системы логирования
        logger_name = (event.data or {}).get('logger_name', '')
        if logger_name in self.LOGGING_SYSTEM_LOGGERS or logger_name.startswith("koru."):
            return
        
        # Форматируем сообщение
        formatted = self.formatter.format(event)
        if not formatted:
            return
        
        # Определяем уровень логирования для вывода
        event_type = event.event_type
        message = f"\n{formatted}"
        
        if event_type == "log.error":
            self.logger.error(message)
        elif event_type == "log.warning":
            self.logger.warning(message)
        elif event_type == "log.debug":
            self.logger.debug(message)
        else:
            self.logger.info(message)
    
    def subscribe(self) -> None:
        """Подписаться на события логирования."""
        self.event_bus.subscribe(EventType.LOG_INFO, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_WARNING, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_ERROR, self.handle_log_event)
    
    def unsubscribe(self) -> None:
        """Отписаться от событий логирования."""
        self.event_bus.unsubscribe(EventType.LOG_INFO, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_DEBUG, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_WARNING, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_ERROR, self.handle_log_event)


# =============================================================================
# FILE HANDLER
# =============================================================================

class FileLogFormatter:
    """
    Форматировщик сообщений для записи в файлы.
    
    Поддерживает форматы:
    - JSON: Pretty-print JSON
    - JSONL: JSON Lines (одна запись на строку)
    """
    
    def __init__(self, config: FileOutputConfig):
        self.config = config
    
    def format(self, event: Event) -> str:
        """Форматирование события для записи в файл."""
        data = event.data or {}
        
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "source": event.source,
            "correlation_id": event.correlation_id,
            **data
        }
        
        if self.config.format == LogFormat.JSON:
            return json.dumps(log_entry, ensure_ascii=False, indent=2)
        else:  # JSONL
            return json.dumps(log_entry, ensure_ascii=False)


class FileLogHandler:
    """
    Обработчик записи логов в файлы.
    
    FEATURES:
    - Автоматическая ротация файлов
    - Организация по сессиям и датам
    - JSON/JSONL формат
    - Потокобезопасная запись
    """
    
    def __init__(
        self,
        event_bus: UnifiedEventBus,
        config: Optional[FileOutputConfig] = None
    ):
        self.event_bus = event_bus
        self.config = config or get_logging_config().file
        self.formatter = FileLogFormatter(self.config)
        self._enabled = True

        # Хранилище ротационных обработчиков
        self._handlers: Dict[str, RotatingFileHandler] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        # Хранилище времени старта сессии для формирования имени папки
        self._session_start_times: Dict[str, datetime] = {}

        # Создание директорий
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """Создание необходимых директорий."""
        if self.config.organize_by_session:
            self.config.base_dir.mkdir(parents=True, exist_ok=True)
            (self.config.base_dir / "sessions").mkdir(exist_ok=True)
        if self.config.organize_by_date:
            (self.config.base_dir / "by_date").mkdir(exist_ok=True)
    
    def _get_handler(self, session_id: str = "common") -> RotatingFileHandler:
        """Получение или создание ротационного обработчика."""
        if session_id not in self._handlers:
            # Сохраняем время старта сессии (первый лог)
            if session_id not in self._session_start_times:
                self._session_start_times[session_id] = datetime.now()
            
            start_time = self._session_start_times[session_id]
            
            # Определение пути к файлу
            if self.config.organize_by_session and session_id != "common":
                # Новый формат: logs/sessions/{date}_{time}_{session_id}/session.log
                date_str = start_time.strftime("%Y-%m-%d")
                time_str = start_time.strftime("%H-%M-%S")
                dir_name = f"{date_str}_{time_str}_{session_id}"
                log_dir = self.config.base_dir / "sessions" / dir_name
                file_name = self.config.session_log_name  # session.log
            else:
                log_dir = self.config.base_dir / "common"
            
            log_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config.organize_by_date:
                date_str = start_time.strftime("%Y-%m-%d")
                file_name = f"{date_str}_{self.config.common_log_name}"
            else:
                file_name = self.config.common_log_name
            
            file_path = log_dir / file_name
            
            # Создание ротационного обработчика (без delay=True чтобы сразу открыть файл)
            handler = RotatingFileHandler(
                file_path,
                maxBytes=self.config.max_file_size_mb * 1024 * 1024,
                backupCount=self.config.backup_count,
                encoding='utf-8',
                delay=False  # Открываем файл сразу
            )
            handler.setLevel(self.config.level.value)
            
            self._handlers[session_id] = handler
            self._locks[session_id] = asyncio.Lock()
        
        return self._handlers[session_id]
    
    async def handle_log_event(self, event: Event) -> None:
        """Обработчик событий логирования для записи в файл."""
        if not self._enabled:
            return

        # Проверка уровня логирования
        data = event.data or {}
        level = data.get("level", "INFO")
        
        # Преобразование уровня логирования в число для сравнения
        level_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        msg_level = level_map.get(level.upper(), 20)  # По умолчанию INFO
        min_level = self.config.level.value  # LogLevel enum value (10, 20, 30, etc.)
        
        if msg_level < min_level:
            return

        # Получение session_id
        session_id = data.get("session_id", "common") or "common"

        # Получение обработчика
        handler = self._get_handler(session_id)
        lock = self._locks.get(session_id)

        # Форматирование сообщения
        formatted = self.formatter.format(event)
        
        # Запись в файл (используем stream вместо write)
        if lock:
            async with lock:
                handler.stream.write(formatted + "\n")
                handler.stream.flush()
        else:
            handler.stream.write(formatted + "\n")
            handler.stream.flush()
    
    def subscribe(self) -> None:
        """Подписаться на события логирования."""
        self.event_bus.subscribe(EventType.LOG_INFO, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_WARNING, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_ERROR, self.handle_log_event)
    
    def unsubscribe(self) -> None:
        """Отписаться от событий логирования."""
        self.event_bus.unsubscribe(EventType.LOG_INFO, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_DEBUG, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_WARNING, self.handle_log_event)
        self.event_bus.unsubscribe(EventType.LOG_ERROR, self.handle_log_event)
    
    def close(self) -> None:
        """Закрытие всех файловых обработчиков."""
        for handler in self._handlers.values():
            handler.close()
        self._handlers.clear()
        self._locks.clear()


# =============================================================================
# FACTORY
# =============================================================================

def setup_logging(event_bus: UnifiedEventBus, config: Optional[LoggingConfig] = None) -> tuple:
    """
    Настройка системы логирования.

    USAGE:
        config = LoggingConfig(
            terminal=TerminalOutputConfig(level=LogLevel.INFO, format=LogFormat.COLORED),
            file=FileOutputConfig(level=LogLevel.DEBUG, format=LogFormat.JSONL)
        )
        terminal_handler, file_handler = setup_logging(event_bus, config)

    ARGS:
        event_bus: Шина событий
        config: Конфигурация (опционально)

    RETURNS:
        (TerminalLogHandler, FileLogHandler) для управления
    """
    if config:
        configure_logging(config)

    terminal_handler = TerminalLogHandler(event_bus)
    file_handler = FileLogHandler(event_bus)

    terminal_handler.subscribe()
    file_handler.subscribe()
    
    # Перехват стандартного logging и направление в EventBus
    event_bus_logging_handler = LoggingToEventBusHandler(event_bus)
    event_bus_logging_handler.setLevel(logging.DEBUG)
    
    # Устанавливаем обработчик на корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(event_bus_logging_handler)

    return terminal_handler, file_handler


def shutdown_logging(file_handler: Optional[FileLogHandler] = None) -> None:
    """
    Корректное завершение системы логирования.
    
    ARGS:
        file_handler: Обработчик файлов для закрытия
    """
    if file_handler:
        file_handler.close()
