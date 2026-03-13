"""
Обработчики событий логирования.

КОМПОНЕНТЫ:
- TerminalLogHandler: вывод в терминал с чистым форматированием
- FileLogHandler: запись в файлы с ротацией

АРХИТЕКТУРА:
- Подписываются на события LOG_* из EventBus
- TerminalLogHandler фильтрует шум и показывает только meaningful execution trace
"""
import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
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
        # info → без иконки (пустая строка по умолчанию)
    }

    def __init__(self):
        self._last_message = None

    def format(self, event, data, level="INFO"):
        """
        Format event for terminal output.
        """
        message = data.get("message") if data else None
        if not message:
            return None

        # suppress duplicates
        if message == self._last_message:
            return None

        self._last_message = message

        # Определяем тип сообщения по компоненту (приоритет) или по тексту
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

        # INFO сообщения — без иконки и префикса
        return message
    
    def _classify_by_component(self, component: str) -> str:
        """
        Классификация по имени компонента (приоритет над текстом).
        
        ARGS:
        - component: Имя компонента из данных события
        
        RETURNS:
        - Тип сообщения или None если не определено
        """
        if not component:
            return None
        
        # Компоненты которые работают с LLM
        if "llm" in component or "provider" in component:
            return "llm"
        
        # Компоненты которые работают с инструментами
        if "tool" in component or "skill" in component:
            return "tool"
        
        # Паттерны поведения
        if "pattern" in component or "behavior" in component:
            return "stage"
        
        # Фабрики и сервисы
        if "factory" in component or "service" in component:
            return "info"
        
        return None

    def _classify(self, message, level):
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

        # LLM классификация — только если слово не в контексте провайдеров/компонентов
        # Избегаем ложных срабатываний на "получены провайдеры: db, llm, ..."
        # и "ComponentFactory: создание компонента"
        if any(k in msg for k in self.LLM_KEYWORDS):
            # Не считаем LLM сообщением если есть слова о провайдерах или компонентах
            if "получен" in msg or "провайдер" in msg or "component" in msg:
                return "info"
            return "llm"

        return "info"


class TerminalLogHandler:
    """
    Clean terminal log handler.

    Displays only meaningful execution trace instead of raw infrastructure logs.
    """

    def __init__(self, event_bus=None, config=None, level="INFO"):
        self.event_bus = event_bus
        self.level = level
        self._formatter = TerminalLogFormatter()
        self._lock = threading.Lock()
        self._enabled = True

        self._level_order = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }

    def enable(self) -> None:
        """Включить вывод логов."""
        self._enabled = True

    def disable(self) -> None:
        """Выключить вывод логов."""
        self._enabled = False

    def handle(self, event, data=None, level="INFO"):
        """
        Process log event and output to terminal.
        """
        if not self._enabled:
            return

        if not self._should_log(level):
            return

        formatted = self._formatter.format(event, data or {}, level)

        if not formatted:
            return

        with self._lock:
            stream = sys.stderr if level in ("ERROR", "CRITICAL") else sys.stdout
            # Используем buffer.write для поддержки emoji в Windows
            try:
                stream.buffer.write((formatted + '\n').encode('utf-8'))
                stream.buffer.flush()
            except (AttributeError, UnicodeEncodeError):
                # Fallback для старых терминалов
                print(formatted, file=stream, flush=True)

        # Добавим принудительную синхронизацию для лучшей последовательности
        if hasattr(stream, 'flush'):
            stream.flush()

    def _should_log(self, level):
        return (
            self._level_order.get(level, 0)
            >= self._level_order.get(self.level, 0)
        )

    async def handle_log_event(self, event):
        """Обработчик событий логирования (для совместимости с EventBus)."""
        if not self._enabled:
            return

        data = event.data or {}
        level = data.get("level", "INFO")

        self.handle(event, data, level)

    def subscribe(self) -> None:
        """Подписаться на события логирования."""
        if self.event_bus:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            self.event_bus.subscribe(EventType.LOG_INFO, self.handle_log_event)
            self.event_bus.subscribe(EventType.LOG_DEBUG, self.handle_log_event)
            self.event_bus.subscribe(EventType.LOG_WARNING, self.handle_log_event)
            self.event_bus.subscribe(EventType.LOG_ERROR, self.handle_log_event)

    def unsubscribe(self) -> None:
        """Отписаться от событий логирования."""
        if self.event_bus:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            self.event_bus.unsubscribe(EventType.LOG_INFO, self.handle_log_event)
            self.event_bus.unsubscribe(EventType.LOG_DEBUG, self.handle_log_event)
            self.event_bus.unsubscribe(EventType.LOG_WARNING, self.handle_log_event)
            self.event_bus.unsubscribe(EventType.LOG_ERROR, self.handle_log_event)


class LoggingToEventBusHandler(logging.Handler):
    """
    Перехватывает стандартные logging записи и публикует их в EventBus.

    Это позволяет использовать новую систему логирования для ВСЕХ логов,
    включая те, что идут через logging.getLogger().info() и т.д.

    ИГНОРИРУЕТ:
    - Сообщения от EventBus internal logger (чтобы избежать цикла)
    - Сообщения от SessionWorker (чтобы избежать цикла)
    - Сообщения от модуля логирования (чтобы избежать цикла)
    """

    # Логгеры которые игнорируются (чтобы избежать бесконечного цикла)
    IGNORED_LOGGERS = {
        "core.infrastructure.event_bus.unified_event_bus.UnifiedEventBus",
        "core.infrastructure.event_bus.unified_event_bus.SessionWorker",
        "EventBusLog",
        "core.infrastructure.logging",  # Игнорируем весь модуль логирования
        "core.infrastructure.logging.handlers",
        "core.infrastructure.logging.config",
        "core.infrastructure.logging.session_log_handler",
    }

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setFormatter(logging.Formatter('%(message)s'))
        self._loop = None

    def _get_loop(self):
        """Получение текущего event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def emit(self, record: logging.LogRecord):
        """Публикация записи логирования в EventBus."""
        try:
            # Игнорируем сообщения от EventBus и логирования (чтобы избежать цикла)
            if record.name in self.IGNORED_LOGGERS or record.name.startswith("core.infrastructure.event_bus"):
                return
            if record.name.startswith("core.infrastructure.logging"):
                return

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

            # Публикуем событие только если есть running loop
            loop = self._get_loop()
            if loop and loop.is_running():
                # Публикация через call_soon_threadsafe для безопасности
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(
                        self.event_bus.publish(event_type, data=data, source=record.name)
                    )
                )

        except Exception:
            # Игнорируем ошибки при закрытии (когда loop уже остановлен)
            pass


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
        # LLM события игнорируются (логируются только в SessionLogHandler)

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
    file_handler = None

    # FileLogHandler ОТКЛЮЧЁН - дублирует SessionLogHandler
    # SessionLogHandler пишет в logs/sessions/{date}_{time}/session.log
    # FileLogHandler создаётся только если включён
    # if config and config.file and config.file.enabled:
    #     file_handler = FileLogHandler(event_bus)
    #     file_handler.subscribe()

    terminal_handler.subscribe()

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
