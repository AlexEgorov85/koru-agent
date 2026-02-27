"""
Логирование через Event Bus.

USAGE:
    from core.infrastructure.event_bus.event_logger import EventLogger
    
    logger = EventLogger("component.name", event_bus)
    logger.info("Сообщение")  # Публикуется событие LOG_INFO
"""
import logging
from typing import Optional, Any, Dict
from core.infrastructure.event_bus.event_bus import EventBus, EventType


class EventLogger:
    """
    Логгер, публикующий сообщения через Event Bus.
    
    Вместо прямого вызова logging.info(), публикует события:
    - LOG_INFO → EventType.LOG_INFO
    - LOG_DEBUG → EventType.LOG_DEBUG
    - LOG_WARNING → EventType.LOG_WARNING
    - LOG_ERROR → EventType.LOG_ERROR
    """

    def __init__(self, name: str, event_bus: Optional[EventBus] = None):
        """
        Инициализация логгера.

        ARGS:
            name: имя логгера (будет включено в данные события)
            event_bus: шина событий (опционально, можно установить позже)
        """
        self.name = name
        self.event_bus = event_bus or get_event_bus()
        self._py_logger = logging.getLogger(name)

    def set_event_bus(self, event_bus: EventBus):
        """Установка шины событий."""
        self.event_bus = event_bus

    def info(self, message: str, **kwargs):
        """
        Публикация события INFO.

        ARGS:
            message: сообщение
            **kwargs: дополнительные данные
        """
        self._publish(EventType.LOG_INFO, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """
        Публикация события DEBUG.

        ARGS:
            message: сообщение
            **kwargs: дополнительные данные
        """
        self._publish(EventType.LOG_DEBUG, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """
        Публикация события WARNING.

        ARGS:
            message: сообщение
            **kwargs: дополнительные данные
        """
        self._publish(EventType.LOG_WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """
        Публикация события ERROR.

        ARGS:
            message: сообщение
            exc_info: включать ли traceback
            **kwargs: дополнительные данные
        """
        data = {"message": message, "logger": self.name, **kwargs}
        if exc_info:
            import traceback
            data["exc_info"] = traceback.format_exc()
        
        self._py_logger.error(message, exc_info=exc_info)
        
        if self.event_bus:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.event_bus.publish(EventType.LOG_ERROR, data, source=self.name)
                    )
                else:
                    loop.run_until_complete(
                        self.event_bus.publish(EventType.LOG_ERROR, data, source=self.name)
                    )
            except RuntimeError:
                # Нет активного event loop
                pass

    def _publish(self, event_type: EventType, message: str, **kwargs):
        """
        Публикация события.

        ARGS:
            event_type: тип события
            message: сообщение
            **kwargs: дополнительные данные
        """
        data = {"message": message, "logger": self.name, **kwargs}
        
        # Дублируем в стандартный логгер для отладки
        self._py_logger.log(
            logging.INFO if event_type == EventType.LOG_INFO else
            logging.DEBUG if event_type == EventType.LOG_DEBUG else
            logging.WARNING,
            message
        )
        
        if self.event_bus:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.event_bus.publish(event_type, data, source=self.name)
                    )
                else:
                    loop.run_until_complete(
                        self.event_bus.publish(event_type, data, source=self.name)
                    )
            except RuntimeError:
                # Нет активного event loop
                pass


# Глобальная шина событий по умолчанию
_default_event_bus: Optional[EventBus] = None


def set_default_event_bus(event_bus: EventBus):
    """Установка глобальной шины событий по умолчанию."""
    global _default_event_bus
    _default_event_bus = event_bus


def get_event_bus() -> Optional[EventBus]:
    """Получение глобальной шины событий по умолчанию."""
    return _default_event_bus


def get_logger(name: str) -> EventLogger:
    """
    Фабричная функция для создания логгера.

    ARGS:
        name: имя логгера

    RETURNS:
        экземпляр EventLogger
    """
    return EventLogger(name)
