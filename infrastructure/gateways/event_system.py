"""
EventSystem - реализация шины событий.
"""
from typing import Any, Dict, List, Callable, Awaitable
from enum import Enum
import asyncio
from datetime import datetime
import logging

from domain.abstractions.event_system import IEventPublisher, EventType, Event


class EventSystem(IEventPublisher):
    """
    Реализация шины событий.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (шлюз)
    - Ответственность: управление событиями и подписками
    - Принципы: соблюдение открытости/закрытости (O в SOLID)
    """
    
    def __init__(self):
        """Инициализация шины событий."""
        self._handlers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        self._global_handlers: List[Callable[[Event], Awaitable[None]]] = []
        self._middleware: List[Callable[[Event], Awaitable[Event]]] = []
        self._enabled = True
        self._logger = logging.getLogger(__name__)
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на событие определенного типа.
        
        Args:
            event_type: Тип события
            handler: Обработчик события
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Отписка от события определенного типа.
        
        Args:
            event_type: Тип события
            handler: Обработчик события
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def subscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на все события.
        
        Args:
            handler: Обработчик события
        """
        if handler not in self._global_handlers:
            self._global_handlers.append(handler)
    
    def unsubscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Отписка от всех событий.
        
        Args:
            handler: Обработчик события
        """
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)
    
    def add_middleware(self, middleware: Callable[[Event], Awaitable[Event]]):
        """
        Добавление middleware для обработки событий.
        
        Args:
            middleware: Middleware-функция
        """
        if middleware not in self._middleware:
            self._middleware.append(middleware)
    
    def remove_middleware(self, middleware: Callable[[Event], Awaitable[Event]]):
        """
        Удаление middleware.
        
        Args:
            middleware: Middleware-функция
        """
        if middleware in self._middleware:
            self._middleware.remove(middleware)
    
    async def _publish_event(self, event: Event) -> None:
        """
        Внутренний метод для публикации события с обработкой middleware.
        """
        if not self._enabled:
            return
        
        try:
            # Применяем middleware
            processed_event = event
            for middleware in self._middleware:
                processed_event = await middleware(processed_event)
                if processed_event is None:
                    # Middleware указал, что событие не должно быть обработано
                    return
            
            # Вызываем глобальных обработчиков
            for handler in self._global_handlers:
                try:
                    await handler(processed_event)
                except Exception as e:
                    self._logger.error(f"Ошибка в глобальном обработчике события: {e}")
            
            # Вызываем обработчиков для конкретного типа события
            handlers = self._handlers.get(processed_event.event_type, [])
            for handler in handlers:
                try:
                    await handler(processed_event)
                except Exception as e:
                    self._logger.error(f"Ошибка в обработчике события {processed_event.event_type}: {e}")
        except Exception as e:
            self._logger.error(f"Ошибка при публикации события: {e}")


    async def publish(self, event_type: EventType, source: str, data: Any) -> None:
        """
        Публикация события.
        
        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        event = Event(event_type=event_type, source=source, data=data)
        await self._publish_event(event)
    
    
    async def publish_simple(self, event_type: EventType, source: str, data: Any) -> None:
        """
        Упрощенная публикация события.
        
        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        event = Event(event_type=event_type, source=source, data=data)
        await self.publish(event)
    
    def enable(self):
        """Включение шины событий."""
        self._enabled = True
    
    def disable(self):
        """Отключение шины событий."""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Проверка, включена ли шина событий."""
        return self._enabled
    
    async def clear_handlers(self, event_type: EventType = None):
        """
        Очистка обработчиков событий.
        
        Args:
            event_type: Тип события для очистки (если None, очищаются все)
        """
        if event_type is None:
            self._handlers.clear()
        else:
            if event_type in self._handlers:
                del self._handlers[event_type]
    
    def get_handler_count(self, event_type: EventType = None) -> int:
        """
        Получение количества обработчиков.
        
        Args:
            event_type: Тип события (если None, возвращается общее количество)
            
        Returns:
            int: Количество обработчиков
        """
        if event_type is None:
            return sum(len(handlers) for handlers in self._handlers.values()) + len(self._global_handlers)
        else:
            return len(self._handlers.get(event_type, []))


# Глобальный экземпляр шины событий
event_system = EventSystem()


def get_event_system() -> EventSystem:
    """
    Функция для получения экземпляра шины событий.
    
    Returns:
        EventSystem: Экземпляр шины событий
    """
    return event_system