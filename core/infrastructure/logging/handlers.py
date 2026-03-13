"""
Обработчики событий логирования.

КОМПОНЕНТЫ:
- TerminalLogHandler: вывод в терминал с чистым форматированием
- LoggingToEventBusHandler: перехват standard logging → EventBus

АРХИТЕКТУРА:
- Подписываются на события LOG_* из EventBus
- TerminalLogHandler фильтрует шум и показывает meaningful execution trace

ПРИМЕЧАНИЕ:
- FileLogHandler УДАЛЁН (дублировал SessionLogHandler)
- Используйте SessionLogHandler для записи в файлы
"""
import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus
from core.config.logging_config import (
    LogFormat,
    LoggingConfig,
    FileConfig,
    get_logging_config,
    configure_logging,
)

# Для обратной совместимости
FileOutputConfig = FileConfig


# ============================================================
# TERMINAL LOG FORMATTER
# ============================================================

class TerminalLogFormatter:
    """
    Smart formatter for terminal logs.

    Converts noisy infrastructure logs into clean agent execution trace.
    """

    STAGE_KEYWORDS = (
        "planning",
        "step",
        "phase",
        "stage",
        "decision",
        "thinking",
    )

    TOOL_KEYWORDS = (
        "tool",
        "capability",
        "executing capability",
        "executing tool",
    )

    RESULT_KEYWORDS = (
        "result",
        "response",
        "output",
        "completed",
        "finished",
        "returned",
    )

    LLM_KEYWORDS = (
        "llm",
        "completion",
        "prompt",
        "generation",
        "gpt",
    )

    ERROR_KEYWORDS = (
        "ошибка",
        "error:",
        "failed to",
        "exception:",
        "произошла ошибка",
        "не удалось",
    )

    ICONS = {
        "stage": "🧠",
        "tool": "🔧",
        "result": "📊",
        "llm": "🤖",
        "error": "❌",
    }

    def __init__(self):
        self._last_message = None

    def format(self, event, data, level="INFO"):
        """Format event for terminal output."""
        message = data.get("message") if data else None
        if not message:
            return None

        if message == self._last_message:
            return None

        self._last_message = message

        component = data.get("component", "").lower() if data else ""
        msg_type = self._classify_by_component(component) or self._classify(message, level)

        icon = self.ICONS.get(msg_type, "")

        if msg_type == "stage":
            return f"\n{icon} {message}"
        if msg_type == "tool":
            return f"{icon} TOOL → {message}"
        if msg_type == "result":
            return f"{icon} RESULT → {message}"
        if msg_type == "llm":
            return f"{icon} LLM → {message}"
        if msg_type == "error":
            return f"\n{icon} ERROR → {message}"

        return message

    def _classify_by_component(self, component: str) -> str:
        """Классификация по имени компонента."""
        if not component:
            return None
        if "llm" in component or "provider" in component:
            return "llm"
        if "tool" in component or "skill" in component:
            return "tool"
        if "pattern" in component or "behavior" in component:
            return "stage"
        if "factory" in component or "service" in component:
            return "info"
        return None

    def _classify(self, message, level):
        """Классификация по тексту сообщения."""
        msg = message.lower()

        if level in ("ERROR", "CRITICAL"):
            return "error"
        if any(k in msg for k in self.ERROR_KEYWORDS):
            return "error"
        if any(k in msg for k in self.STAGE_KEYWORDS):
            return "stage"
        if any(k in msg for k in self.TOOL_KEYWORDS):
            return "tool"
        if any(k in msg for k in self.RESULT_KEYWORDS):
            return "result"
        if any(k in msg for k in self.LLM_KEYWORDS):
            if "получен" in msg or "провайдер" in msg or "component" in msg:
                return "info"
            return "llm"
        return "info"


# ============================================================
# TERMINAL LOG HANDLER
# ============================================================

class TerminalLogHandler:
    """
    Clean terminal log handler.

    Displays only meaningful execution trace instead of raw infrastructure logs.
    """

    def __init__(self, event_bus: UnifiedEventBus):
        self.event_bus = event_bus
        self.formatter = TerminalLogFormatter()
        self._enabled = True

    def subscribe(self):
        """Подписка на события логирования."""
        self.event_bus.subscribe(EventType.LOG_INFO, self._on_log)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self._on_log)
        self.event_bus.subscribe(EventType.LOG_WARNING, self._on_log)
        self.event_bus.subscribe(EventType.LOG_ERROR, self._on_error)

    async def _on_log(self, event: Event):
        """Обработка логов INFO/DEBUG/WARNING."""
        if not self._enabled:
            return

        data = event.data or {}
        message = self.formatter.format(event, data, data.get("level", "INFO"))

        if message:
            print(message, flush=True)

    async def _on_error(self, event: Event):
        """Обработка ERROR логов."""
        if not self._enabled:
            return

        data = event.data or {}
        message = self.formatter.format(event, data, data.get("level", "ERROR"))

        if message:
            print(message, file=sys.stderr, flush=True)

    def close(self):
        """Закрытие обработчика."""
        self._enabled = False


# ============================================================
# STANDARD LOGGING → EVENTBUS HANDLER
# ============================================================

class LoggingToEventBusHandler(logging.Handler):
    """
    Перехват стандартного logging и направление в EventBus.

    IGNORED_LOGGERS:
    - event_bus — предотвращение циклических зависимостей
    - logging.* — предотвращение рекурсии
    """

    IGNORED_LOGGERS = {
        "core.infrastructure.event_bus.unified_event_bus.UnifiedEventBus",
        "core.infrastructure.event_bus.unified_event_bus.SessionWorker",
        "EventBusLog",
        "core.infrastructure.logging",
        "core.infrastructure.logging.handlers",
        "core.infrastructure.logging.session_log_handler",
    }

    def __init__(self, event_bus: UnifiedEventBus):
        super().__init__()
        self.event_bus = event_bus
        self._loop = None
        self._loop_lock = threading.Lock()

    def emit(self, record):
        """Emit a record via EventBus."""
        try:
            if record.name in self.IGNORED_LOGGERS:
                return

            event_type_str = getattr(record, 'event_type', None)
            if event_type_str and isinstance(event_type_str, str):
                event_type = {
                    "log.info": EventType.LOG_INFO,
                    "log.debug": EventType.LOG_DEBUG,
                    "log.warning": EventType.LOG_WARNING,
                    "log.error": EventType.LOG_ERROR,
                }.get(event_type_str, EventType.LOG_INFO)
            else:
                event_type = {
                    logging.INFO: EventType.LOG_INFO,
                    logging.DEBUG: EventType.LOG_DEBUG,
                    logging.WARNING: EventType.LOG_WARNING,
                    logging.ERROR: EventType.LOG_ERROR,
                    logging.CRITICAL: EventType.LOG_ERROR,
                }.get(record.levelno, EventType.LOG_INFO)

            data = {
                "message": self.format(record),
                "level": record.levelname,
                "component": record.name,
                "logger_name": record.name,
            }

            loop = self._get_loop()
            if loop and loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(
                        self.event_bus.publish(event_type, data=data, source=record.name)
                    )
                )

        except Exception:
            pass  # Игнорируем ошибки при закрытии

    def _get_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Получение event loop."""
        if self._loop is not None:
            return self._loop

        with self._loop_lock:
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
            return self._loop


# ============================================================
# SETUP / SHUTDOWN
# ============================================================

def setup_logging(
    event_bus: UnifiedEventBus,
    config: Optional[LoggingConfig] = None
):
    """
    Настройка обработчиков логирования.

    ARGS:
    - event_bus: Шина событий
    - config: Конфигурация (не используется, оставлена для совместимости)

    RETURNS:
    - terminal_handler: TerminalLogHandler
    """
    config = config or get_logging_config()

    terminal_handler = TerminalLogHandler(event_bus)

    # Подписка на события
    terminal_handler.subscribe()

    # Перехват стандартного logging
    event_bus_logging_handler = LoggingToEventBusHandler(event_bus)
    event_bus_logging_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(event_bus_logging_handler)

    return terminal_handler, None  # file_handler удалён


def shutdown_logging(file_handler=None) -> None:
    """
    Корректное завершение системы логирования.

    ARGS:
    - file_handler: Не используется (удалён)
    """
    # FileLogHandler удалён - ничего закрывать не нужно
    pass


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    # Formatters
    'TerminalLogFormatter',
    
    # Handlers
    'TerminalLogHandler',
    'LoggingToEventBusHandler',
    
    # Setup
    'setup_logging',
    'shutdown_logging',
    
    # Backward compatibility
    'FileOutputConfig',
    'FileLogFormatter',  # Заглушка
    'FileLogHandler',    # Заглушка
]


# ============================================================
# STUBS FOR BACKWARD COMPATIBILITY
# ============================================================

class FileLogFormatter:
    """Заглушка: FileLogFormatter удалён (дублировал SessionLogHandler)."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("FileLogFormatter удалён. Используйте SessionLogHandler.")


class FileLogHandler:
    """Заглушка: FileLogHandler удалён (дублировал SessionLogHandler)."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("FileLogHandler удалён. Используйте SessionLogHandler.")
