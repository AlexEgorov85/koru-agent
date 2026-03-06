"""
Интерфейс для шины событий.

Определяет контракт для всех реализаций Event Bus.
"""

from typing import Protocol, Any, Dict, Optional, Callable, List
from datetime import datetime


class EventBusInterface(Protocol):
    """
    Интерфейс для шины событий.

    АБСТРАКЦИЯ: Определяет что нужно для публикации и подписки на события.
    РЕАЛИЗАЦИИ: UnifiedEventBus, EventBusConcurrent.
    """

    async def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие.

        ARGS:
        - event_type: Тип события
        - data: Данные события
        - source: Источник события
        - session_id: ID сессии для маршрутизации
        """
        ...

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        session_id: Optional[str] = None
    ) -> None:
        """
        Подписаться на событие.

        ARGS:
        - event_type: Тип события
        - handler: Функция-обработчик
        - session_id: ID сессии для фильтрации
        """
        ...

    def unsubscribe(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Отписаться от события.

        ARGS:
        - event_type: Тип события
        - handler: Функция-обработчик
        """
        ...

    async def start_workers(self) -> None:
        """Запустить worker'ы для обработки событий."""
        ...

    async def shutdown(self) -> None:
        """Завершить работу шины событий."""
        ...

    @property
    def stats(self) -> Dict[str, Any]:
        """Получить статистику шины событий."""
        ...
