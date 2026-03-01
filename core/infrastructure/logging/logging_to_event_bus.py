"""
LoggingToEventBusHandler - перенаправляет стандартный logging в EventBus.

ИСПОЛЬЗОВАНИЕ:
    # При инициализации приложения
    event_bus = get_event_bus()
    handler = LoggingToEventBusHandler(event_bus)
    logging.getLogger().addHandler(handler)

Теперь все вызовы logger.info/error/debug/warning будут публиковаться в EventBus
и форматироваться через EventBusLogHandler.
"""
import logging
import asyncio
from typing import Optional
from core.infrastructure.event_bus.event_bus import EventBus, EventType


class LoggingToEventBusHandler(logging.Handler):
    """
    Logging handler который публикует записи в EventBus.
    
    Все вызовы logger.info/error/debug/warning перенаправляются в EventBus
    и затем форматируются через EventBusLogHandler.
    """
    
    def __init__(self, event_bus: EventBus, source: str = "app"):
        """
        Инициализация обработчика.
        
        ARGS:
            event_bus: шина событий для публикации
            source: источник событий (по умолчанию "app")
        """
        super().__init__()
        self.event_bus = event_bus
        self.source = source
        self.setLevel(logging.DEBUG)  # Перехватываем все уровни
    
    def emit(self, record: logging.LogRecord):
        """
        Публикация записи лога в EventBus.
        
        ARGS:
            record: запись лога от logging
        """
        try:
            # Получаем сообщение
            message = self.format(record)
            
            # Определяем уровень
            level_name = record.levelname.lower()
            if level_name == 'critical':
                level_name = 'error'
            
            # Маппинг уровней logging на EventType
            event_type_map = {
                'debug': EventType.LOG_DEBUG,
                'info': EventType.LOG_INFO,
                'warning': EventType.LOG_WARNING,
                'error': EventType.LOG_ERROR,
                'critical': EventType.LOG_ERROR,
            }
            
            event_type = event_type_map.get(level_name, EventType.LOG_INFO)
            
            # Формируем данные события
            data = {
                "message": message,
                "level": record.levelname,
                "logger_name": record.name,
                "source": self.source,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Публикуем в EventBus (асинхронно)
            # Используем create_task так как emit() синхронный
            asyncio.create_task(
                self.event_bus.publish(event_type, data=data, source=self.source)
            )
            
        except Exception as e:
            # Если ошибка при публикации - пишем в stderr
            self.handleError(record)
            print(f"LoggingToEventBusHandler error: {e}")


def setup_logging_to_event_bus(event_bus: EventBus, source: str = "app", level: int = logging.INFO) -> LoggingToEventBusHandler:
    """
    Настройка перенаправления logging в EventBus.
    
    USAGE:
        from core.infrastructure.logging.logging_to_event_bus import setup_logging_to_event_bus
        
        event_bus = get_event_bus()
        handler = setup_logging_to_event_bus(event_bus, source="my_app")
        logging.getLogger().addHandler(handler)
    
    ARGS:
        event_bus: шина событий
        source: источник событий
        level: минимальный уровень логирования
    
    RETURNS:
        LoggingToEventBusHandler для возможного удаления позже
    """
    handler = LoggingToEventBusHandler(event_bus, source=source)
    handler.setLevel(level)
    
    # Добавляем formatter если нужно
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    return handler
