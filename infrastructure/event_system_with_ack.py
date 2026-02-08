"""
EventSystem with acknowledgment mechanism for reliable event delivery.
This extends the basic EventSystem with confirmation tracking and retry logic.
"""

from typing import Any, Dict, List, Callable, Awaitable, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging

from domain.abstractions.event_types import Event, EventType, IEventPublisher
from infrastructure.event_system import (
    IEventFilter, IEventValidator, IRateLimiter, 
    SecurityEventFilter, SizeLimitFilter, EventValidator, 
    TokenBucketRateLimiter
)


class EventStatus(Enum):
    """Статусы для отслеживания состояния события"""
    PENDING = "pending"      # Событие отправлено, но еще не подтверждено
    CONFIRMED = "confirmed"  # Событие подтверждено всеми обработчиками
    FAILED = "failed"        # Событие не было обработано успешно
    RETRYING = "retrying"    # Событие находится в процессе повторной отправки


@dataclass
class TrackedEvent:
    """Обертка для отслеживания статуса события"""
    event: Event
    status: EventStatus = EventStatus.PENDING
    handlers_confirmed: Set[str] = field(default_factory=set)  # Подтвердившие обработчики
    handlers_total: int = 0  # Общее количество обработчиков
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_retry_at: Optional[datetime] = None


class AcknowledgedEventSystem(IEventPublisher):
    """
    Система событий с подтверждением доставки.
    Обеспечивает надежную доставку событий с механизмом подтверждения и повторных попыток.
    """

    def __init__(
        self,
        filters: Optional[List[IEventFilter]] = None,
        validators: Optional[List[IEventValidator]] = None,
        rate_limiter: Optional[IRateLimiter] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """Инициализация системы событий с подтверждением."""
        self._handlers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        self._global_handlers: List[Callable[[Event], Awaitable[None]]] = []
        self._tracked_events: Dict[str, TrackedEvent] = {}
        self._handler_registry: Dict[str, Callable] = {}  # Регистрация обработчиков
        self._filters = filters or []
        self._validators = validators or []
        self._rate_limiter = rate_limiter
        self._enabled = True
        self._logger = logging.getLogger(__name__)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        
        # Запуск фоновой задачи для обработки retry
        self._retry_task = None
        self._running = False

    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на события определенного типа.

        Args:
            event_type: Тип события для подписки
            handler: Обработчик события
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Отписка от событий определенного типа.

        Args:
            event_type: Тип события
            handler: Обработчик для удаления
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def subscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на все события.

        Args:
            handler: Обработчик для всех событий
        """
        if handler not in self._global_handlers:
            self._global_handlers.append(handler)

    def unsubscribe_global(self, handler: Callable[[Event], Awaitable[None]]):
        """
        Отписка от всех событий.

        Args:
            handler: Обработчик для удаления из глобальной подписки
        """
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)

    def subscribe_with_ack(self, event_type: EventType, handler: Callable[[Event], Awaitable[bool]]):
        """
        Подписка на событие с подтверждением (возвращает True если обработка успешна)
        
        Args:
            event_type: Тип события
            handler: Обработчик, возвращающий True при успешной обработке
        """
        # Регистрируем обработчик для возможности подтверждения
        handler_id = f"{event_type.value}_{hash(handler)}"
        self._handler_registry[handler_id] = handler
        
        # Оборачиваем обработчик для подтверждения
        async def wrapped_handler(event: Event) -> None:
            try:
                success = await handler(event)
                if success:
                    await self.confirm_event_delivery(event.id, handler_id)
            except Exception as e:
                # В случае ошибки не подтверждаем доставку
                self._logger.error(f"Error in handler {handler_id}: {e}", exc_info=True)
        
        self.subscribe(event_type, wrapped_handler)

    async def _validate_event(self, event: Event) -> bool:
        """Валидация события через все зарегистрированные валидаторы."""
        for validator in self._validators:
            if not await validator.validate(event):
                return False
        return True

    async def _filter_event(self, event: Event) -> Optional[Event]:
        """Применение всех зарегистрированных фильтров к событию."""
        filtered_event = event
        for event_filter in self._filters:
            filtered_event = await event_filter.filter(filtered_event)
            if filtered_event is None:
                return None
        return filtered_event

    async def publish(self, event_type: EventType, source: str, data: Any) -> None:
        """
        Публикация события без отслеживания подтверждения.

        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        if not self._enabled:
            return

        # Создание события
        event = Event(event_type=event_type, source=source, data=data)

        # Применение ограничения скорости, если настроено
        if self._rate_limiter:
            if not await self._rate_limiter.allow_request():
                self._logger.warning(f"Event dropped due to rate limiting: {event.id}")
                return

        # Валидация события
        if not await self._validate_event(event):
            self._logger.warning(f"Event validation failed: {event.id}")
            return

        # Применение фильтров
        filtered_event = await self._filter_event(event)
        if filtered_event is None:
            self._logger.info(f"Event filtered out: {event.id}")
            return

        # Публикация события
        await self._publish_event_internal(filtered_event)

    async def publish_with_ack(self, event_type: EventType, source: str, data: Any) -> str:
        """
        Публикация события с отслеживанием подтверждения
        
        Returns:
            str: ID события для последующего отслеживания
        """
        if not self._enabled:
            raise RuntimeError("Event system is disabled")

        # Создание события
        event = Event(event_type=event_type, source=source, data=data)

        # Применение ограничения скорости, если настроено
        if self._rate_limiter:
            if not await self._rate_limiter.allow_request():
                self._logger.warning(f"Event dropped due to rate limiting: {event.id}")
                raise RuntimeError(f"Rate limit exceeded for event: {event.id}")

        # Валидация события
        if not await self._validate_event(event):
            self._logger.warning(f"Event validation failed: {event.id}")
            raise RuntimeError(f"Event validation failed: {event.id}")

        # Применение фильтров
        filtered_event = await self._filter_event(event)
        if filtered_event is None:
            self._logger.info(f"Event filtered out: {event.id}")
            raise RuntimeError(f"Event filtered out: {event.id}")

        # Находим всех обработчиков для этого типа события
        handlers = self._handlers.get(event_type, [])
        handler_ids = [f"{event_type.value}_{hash(h)}" for h in handlers]
        
        # Создаем отслеживаемое событие
        tracked_event = TrackedEvent(
            event=filtered_event,
            handlers_total=len(handlers),
            handlers_confirmed=set()
        )
        
        self._tracked_events[event.id] = tracked_event
        
        # Публикуем событие внутренним методом
        await self._publish_event_internal(filtered_event)
        
        return event.id

    async def _publish_event_internal(self, event: Event) -> None:
        """Внутренний метод публикации события подписчикам."""
        try:
            # Вызов глобальных обработчиков
            for handler in self._global_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error(f"Error in global event handler: {e}", exc_info=True)

            # Вызов обработчиков конкретного типа
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error(f"Error in event handler for {event.event_type}: {e}", exc_info=True)
        except Exception as e:
            self._logger.error(f"Error publishing event: {e}", exc_info=True)

    async def confirm_event_delivery(self, event_id: str, handler_id: str) -> bool:
        """
        Подтверждение доставки события конкретным обработчиком
        
        Args:
            event_id: ID события
            handler_id: ID обработчика
            
        Returns:
            bool: True если подтверждение принято, False если событие не найдено
        """
        if event_id not in self._tracked_events:
            return False
            
        tracked_event = self._tracked_events[event_id]
        
        # Добавляем обработчик к подтвердившим
        tracked_event.handlers_confirmed.add(handler_id)
        
        # Проверяем, все ли обработчики подтвердили
        if len(tracked_event.handlers_confirmed) >= tracked_event.handlers_total:
            tracked_event.status = EventStatus.CONFIRMED
            # Удаляем из отслеживания если все подтвердили
            del self._tracked_events[event_id]
            
        return True

    async def get_event_status(self, event_id: str) -> Optional[EventStatus]:
        """Получение статуса события"""
        if event_id in self._tracked_events:
            return self._tracked_events[event_id].status
        return None

    async def get_unconfirmed_events(self) -> List[TrackedEvent]:
        """Получение списка неподтвержденных событий"""
        return [
            te for te in self._tracked_events.values()
            if te.status in [EventStatus.PENDING, EventStatus.RETRYING]
        ]

    async def start_retry_monitoring(self):
        """Запуск фонового процесса для повторной отправки неподтвержденных событий"""
        if self._retry_task is None:
            self._running = True
            self._retry_task = asyncio.create_task(self._retry_loop())

    async def stop_retry_monitoring(self):
        """Остановка фонового процесса"""
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

    async def _retry_loop(self):
        """Фоновый цикл для повторной отправки неподтвержденных событий"""
        while self._running:
            try:
                # Получаем неподтвержденные события
                unconfirmed = await self.get_unconfirmed_events()
                
                for tracked_event in unconfirmed:
                    # Проверяем, нужно ли повторить отправку
                    if (tracked_event.retry_count < self._max_retries and 
                        (tracked_event.last_retry_at is None or 
                         datetime.now() - tracked_event.last_retry_at > timedelta(seconds=self._retry_delay))):
                        
                        # Меняем статус на retrying
                        tracked_event.status = EventStatus.RETRYING
                        tracked_event.retry_count += 1
                        tracked_event.last_retry_at = datetime.now()
                        
                        # Повторно публикуем событие
                        await self._publish_event_internal(tracked_event.event)
                
                await asyncio.sleep(self._retry_delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in retry loop: {e}", exc_info=True)
                await asyncio.sleep(self._retry_delay)

    def enable(self):
        """Включение системы событий."""
        self._enabled = True

    def disable(self):
        """Отключение системы событий."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Проверка, включена ли система событий."""
        return self._enabled

    def add_filter(self, event_filter: IEventFilter):
        """Добавление фильтра в систему событий."""
        if event_filter not in self._filters:
            self._filters.append(event_filter)

    def remove_filter(self, event_filter: IEventFilter):
        """Удаление фильтра из системы событий."""
        if event_filter in self._filters:
            self._filters.remove(event_filter)

    def add_validator(self, validator: IEventValidator):
        """Добавление валидатора в систему событий."""
        if validator not in self._validators:
            self._validators.append(validator)

    def remove_validator(self, validator: IEventValidator):
        """Удаление валидатора из системы событий."""
        if validator in self._validators:
            self._validators.remove(validator)


# Глобальный экземпляр для обратной совместимости во время миграции
ack_event_system = AcknowledgedEventSystem(
    filters=[SecurityEventFilter(), SizeLimitFilter()],
    validators=[EventValidator()],
    rate_limiter=TokenBucketRateLimiter(requests_per_second=100.0, burst_capacity=200),
    max_retries=3,
    retry_delay=5.0
)


def get_ack_event_system() -> AcknowledgedEventSystem:
    """
    Получение экземпляра системы событий с подтверждением
    
    Returns:
        AcknowledgedEventSystem: Экземпляр системы событий с подтверждением
    """
    return ack_event_system