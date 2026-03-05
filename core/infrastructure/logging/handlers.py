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
import sys
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
    
    ИГНОРИРУЕТ:
    - Сообщения от EventBus internal logger (чтобы избежать цикла)
    - Сообщения от SessionWorker (чтобы избежать цикла)
    """

    # Логгеры которые игнорируются (чтобы избежать бесконечного цикла)
    IGNORED_LOGGERS = {
        "core.infrastructure.event_bus.unified_event_bus.UnifiedEventBus",
        "core.infrastructure.event_bus.unified_event_bus.SessionWorker",
        "EventBusLog",
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
            # Игнорируем сообщения от EventBus (чтобы избежать цикла)
            if record.name in self.IGNORED_LOGGERS or record.name.startswith("core.infrastructure.event_bus"):
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


class TerminalLogFormatter:
    """
    Форматировщик сообщений для терминала.

    Поддерживает несколько форматов:
    - SIMPLE: [INFO] message
    - DETAILED: [2024-01-01 12:00:00] [INFO] [component] message
    """

    def __init__(self, config: TerminalOutputConfig):
        self.config = config
        self._message_count = 0

    def format(self, event: Event) -> Optional[str]:
        """
        Форматирование события для вывода в терминал.

        RETURNS:
            Отформатированная строка или None если сообщение не должно выводиться
        """
        data = event.data or {}
        # Преобразуем event_type в строку если это Enum
        event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        message_type = data.get("type", event_type_str)
        level = data.get("level", "INFO")

        # Проверка фильтров
        if not self._should_log(event, message_type, level):
            return None

        # Форматирование в зависимости от типа
        if self.config.format == LogFormat.SIMPLE:
            return self._format_simple(event, data, level)
        else:  # DETAILED
            return self._format_detailed(event, data, level)
    
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


class TerminalLogHandler:
    """
    Обработчик вывода логов в терминал.

    ПОДПИСЫВАЕТСЯ НА:
    - LOG_INFO, LOG_DEBUG, LOG_WARNING, LOG_ERROR

    FEATURES:
    - Простой текстовый вывод
    - Гибкие фильтры по компонентам и типам событий
    - Несколько форматов вывода
    """

    # Логгеры системы логирования (игнорируем чтобы избежать цикла и дублирования)
    LOGGING_SYSTEM_LOGGERS = {
        "EventBusLog",
        "EventBus",
        "SessionWorker",
        "ResourceDiscovery",
        "DataRepository",
        "ApplicationContext",
        "LifecycleManager",
        "MetricsCollector",
        "LogCollector",
        "PromptStorage",
        "ContractStorage",
        "core.infrastructure.discovery.resource_discovery",
    }
    
    # Типы событий которые не нужно выводить в терминал (чтобы избежать цикла и дублирования)
    SKIP_EVENT_TYPES = {
        "metric.collected",
    }
    
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

        # Преобразуем event_type в строку для сравнения
        event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

        # Игнорируем события от логгеров системы логирования
        logger_name = (event.data or {}).get('logger_name', '')
        if logger_name in self.LOGGING_SYSTEM_LOGGERS or logger_name.startswith("koru.") or logger_name.startswith("core.infrastructure.discovery"):
            return

        # Игнорируем метрики события (они логируются отдельно в SessionLogHandler)
        if event_type_str in self.SKIP_EVENT_TYPES:
            return

        # Форматируем сообщение
        formatted = self.formatter.format(event)
        if not formatted:
            return

        # Определяем уровень логирования для вывода
        message = f"\n{formatted}"

        if event_type_str == "log.error":
            self.logger.error(message)
        elif event_type_str == "log.warning":
            self.logger.warning(message)
        elif event_type_str == "log.debug":
            self.logger.debug(message)
        else:
            self.logger.info(message)

    def subscribe(self) -> None:
        """Подписаться на события логирования."""
        self.event_bus.subscribe(EventType.LOG_INFO, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_WARNING, self.handle_log_event)
        self.event_bus.subscribe(EventType.LOG_ERROR, self.handle_log_event)
        # LLM события обрабатываются через SessionLogHandler

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
    file_handler = None
    
    # FileLogHandler создаётся только если включён
    if config and config.file and config.file.enabled:
        file_handler = FileLogHandler(event_bus)
        file_handler.subscribe()

    terminal_handler.subscribe()

    # Перехват стандартного logging и направление в EventBus
    event_bus_logging_handler = LoggingToEventBusHandler(event_bus)
    event_bus_logging_handler.setLevel(logging.DEBUG)

    # Устанавливаем обработчик на корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(event_bus_logging_handler)
    
    # Добавляем консольный обработчик для EventBusLog (чтобы вывод в терминал работал)
    event_bus_logger = logging.getLogger("EventBusLog")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    event_bus_logger.addHandler(console_handler)

    return terminal_handler, file_handler


def shutdown_logging(file_handler: Optional[FileLogHandler] = None) -> None:
    """
    Корректное завершение системы логирования.
    
    ARGS:
        file_handler: Обработчик файлов для закрытия
    """
    if file_handler:
        file_handler.close()
