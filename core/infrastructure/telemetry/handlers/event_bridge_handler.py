"""
Logging to EventBridge Handler — перехват standard logging → EventBus.

FEATURES:
- Перехватывает logging module
- Направляет в EventBus
- Игнорирует внутренние логгеры
"""
import asyncio
import logging
import threading
from typing import Optional

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


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
        "core.infrastructure.telemetry",
    }

    def __init__(self, event_bus: UnifiedEventBus):
        super().__init__()
        self.event_bus = event_bus
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_lock = threading.Lock()
        self._installed = False

    def emit(self, record):
        """Emit a record via EventBus."""
        try:
            if record.name in self.IGNORED_LOGGERS:
                return

            # Определение типа события
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
            }

            # Публикация
            loop = self._get_loop()
            if loop and loop.is_running():
                from concurrent.futures import Future
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.event_bus.publish(event_type, data=data, source=record.name),
                        loop
                    )
                except Exception:
                    pass  # Fallback

        except Exception:
            pass  # Игнорируем ошибки

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

    def install(self):
        """Установка обработчика в root logger."""
        if not self._installed:
            root_logger = logging.getLogger()
            root_logger.addHandler(self)
            self.setLevel(logging.DEBUG)
            self._installed = True

    def uninstall(self):
        """Удаление обработчика из root logger."""
        if self._installed:
            try:
                root_logger = logging.getLogger()
                root_logger.removeHandler(self)
            except Exception:
                pass
            self._installed = False


__all__ = ['LoggingToEventBusHandler']
