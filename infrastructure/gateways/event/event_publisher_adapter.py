
from domain.abstractions.event_types import Event, EventType, IEventPublisher
from infrastructure.gateways.event_system import EventSystem
from typing import Any, Callable, Awaitable


class EventPublisherAdapter(IEventPublisher):
    """
    Адаптер для преобразования конкретной реализации EventSystem в интерфейс IEventPublisher.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (адаптер)
    - Зависимости: от конкретной реализации EventSystem и доменных абстракций
    - Ответственность: обеспечение соответствия контракту IEventPublisher
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self, event_system: EventSystem):
        """
        Инициализация адаптера.
        
        Args:
            event_system: Конкретная реализация EventSystem
        """
        self._event_system = event_system
    
    async def publish(self, event_type: EventType, source: str, data: Any):
        """
        Публикация события через адаптированную реализацию.
        
        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        event = Event(event_type=event_type, source=source, data=data)
        await self._event_system.publish(event)
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на событие определенного типа.
        
        Args:
            event_type: Тип события
            handler: Обработчик события
        """
        self._event_system.subscribe(event_type, handler)