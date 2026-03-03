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
)


# =============================================================================
# TERMINAL HANDLER
# =============================================================================

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
        "log.debug": "🔍",
        "log.warning": "⚠️",
        "log.error": "❌",
        "llm.call.start": "🔄",
        "llm.call.success": "✅",
        "llm.call.error": "❌",
        "reasoning.start": "🧠",
        "reasoning.complete": "💡",
        "decision.made": "🎯",
        "agent.start": "🤖",
        "agent.complete": "🏁",
        "agent.error": "💥",
    }
    
    TYPE_COLORS = {
        "llm.call.start": LogColors.LLM,
        "llm.call.success": LogColors.SUCCESS,
        "llm.call.error": LogColors.ERROR,
        "reasoning.start": LogColors.REASONING,
        "reasoning.complete": LogColors.SUCCESS,
        "decision.made": LogColors.DECISION,
        "agent.start": LogColors.AGENT,
        "agent.complete": LogColors.SUCCESS,
        "agent.error": LogColors.ERROR,
    }
    
    def __init__(self, config: TerminalOutputConfig):
        self.config = config
        self._use_colors = config.format == LogFormat.COLORED
    
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
        level_priority = {
            "DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4
        }
        min_level = self.config.level.value
        msg_level = level_priority.get(level.upper(), 1)
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
        """Цветной формат с иконками."""
        c = LogColors
        
        # Иконка и цвет
        icon = self.TYPE_ICONS.get(message_type, "•")
        color = self.TYPE_COLORS.get(message_type, self._get_level_color(level))
        
        message = data.get("message", str(event.data)) if event.data else str(event)
        component = data.get("component", "") if event.data else ""
        session_id = data.get("session_id", "") if event.data else ""
        agent_id = data.get("agent_id", "") if event.data else ""
        
        lines = []
        
        # Заголовок с типом сообщения
        if self._use_colors:
            header = f"{color}{c.BOLD}[{icon} {message_type}]{c.RESET}"
        else:
            header = f"[{icon} {message_type}]"
        
        lines.append(header)
        lines.append(f"  {c.DIM}└─{c.RESET} {message}")
        
        # Контекст
        context_parts = []
        if self.config.show_session_info:
            if session_id and session_id != "system":
                context_parts.append(f"session={session_id}")
            if agent_id and agent_id != "system":
                context_parts.append(f"agent={agent_id}")
        if self.config.show_source and component:
            context_parts.append(f"component={component}")
        
        if context_parts:
            lines.append(f"  {c.DIM}└─{c.RESET} {c.DIM}{' | '.join(context_parts)}{c.RESET}")
        
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
            # Определение пути к файлу
            if self.config.organize_by_session and session_id != "common":
                log_dir = self.config.base_dir / "sessions" / session_id
            else:
                log_dir = self.config.base_dir / "common"
            
            log_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config.organize_by_date:
                date_str = datetime.now().strftime("%Y-%m-%d")
                file_name = f"{date_str}_{self.config.session_log_name if session_id != 'common' else self.config.common_log_name}"
            else:
                file_name = self.config.session_log_name if session_id != "common" else self.config.common_log_name
            
            file_path = log_dir / file_name
            
            # Создание ротационного обработчика
            handler = RotatingFileHandler(
                file_path,
                maxBytes=self.config.max_file_size_mb * 1024 * 1024,
                backupCount=self.config.backup_count,
                encoding='utf-8',
                delay=True
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
        level_priority = {
            "DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4
        }
        min_level = self.config.level.value
        msg_level = level_priority.get(level.upper(), 1)
        if msg_level < min_level:
            return
        
        # Получение session_id
        session_id = data.get("session_id", "common") or "common"
        
        # Получение обработчика
        handler = self._get_handler(session_id)
        lock = self._locks.get(session_id)
        
        if lock:
            async with lock:
                formatted = self.formatter.format(event)
                handler.write(formatted + "\n")
                handler.flush()
        else:
            formatted = self.formatter.format(event)
            handler.write(formatted + "\n")
            handler.flush()
    
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
    
    return terminal_handler, file_handler


def shutdown_logging(file_handler: Optional[FileLogHandler] = None) -> None:
    """
    Корректное завершение системы логирования.
    
    ARGS:
        file_handler: Обработчик файлов для закрытия
    """
    if file_handler:
        file_handler.close()
