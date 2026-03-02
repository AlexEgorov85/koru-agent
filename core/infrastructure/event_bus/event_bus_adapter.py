"""
Адаптер для плавной миграции на UnifiedEventBus.

НАЗНАЧЕНИЕ:
- Эмулирует старый API EventBusManager и EventBus
- Позволяет постепенную миграцию компонентов
- Будет удалён на Этапе 4 после полной миграции

WARNING: Этот класс временный и будет удалён после завершения миграции!

USAGE:
```python
# Вместо старого кода:
from core.infrastructure.event_bus.domain_event_bus import get_event_bus_manager
manager = get_event_bus_manager()
agent_bus = manager.get_bus(EventDomain.AGENT)
agent_bus.subscribe(EventType.AGENT_STARTED, handler)

# Временный адаптер:
from core.infrastructure.event_bus.event_bus_adapter import EventBusAdapter
from core.infrastructure.event_bus.unified_event_bus import get_event_bus

unified_bus = get_event_bus()
adapter = EventBusAdapter(unified_bus)

# Старый API работает через адаптер
agent_bus = adapter.get_bus(EventDomain.AGENT)
agent_bus.subscribe(EventType.AGENT_STARTED, handler)
```
"""
import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from .unified_event_bus import (
    UnifiedEventBus,
    Event,
    EventType,
    EventDomain,
    get_event_domain,
)


logger = logging.getLogger(__name__)


class DomainEventBusProxy:
    """
    Прокси для эмуляции DomainEventBus через UnifiedEventBus.

    WARNING: Временный класс для обратной совместимости!
    """

    def __init__(self, unified_bus: UnifiedEventBus, domain: EventDomain):
        self.domain = domain
        self._unified_bus = unified_bus
        self._enabled = True
        self._event_count = 0
        self._error_count = 0
        self._logger = logging.getLogger(f"{__name__}.DomainEventBusProxy[{domain.value}]")

    def subscribe(self, event_type: Union[str, EventType], handler: Callable):
        """Подписка на событие в рамках домена."""
        self._unified_bus.subscribe(event_type, handler, domain=self.domain)
        self._logger.debug(f"Подписан обработчик на {event_type} (domain={self.domain.value})")

    def subscribe_all(self, handler: Callable):
        """Подписка на все события домена."""
        # Для прокси subscribe_all подписываемся на все события с фильтром по домену
        self._unified_bus.subscribe_all(handler, domains=[self.domain])

    def unsubscribe(self, event_type: Union[str, EventType], handler: Callable):
        """Отписка от события."""
        self._unified_bus.unsubscribe(event_type, handler)

    async def publish(
        self,
        event: Union[Event, str, EventType],
        data: Dict[str, Any] = None,
        source: str = "",
        correlation_id: str = ""
    ) -> bool:
        """Публикация события в домене."""
        if not self._enabled:
            self._logger.debug(f"Домен {self.domain.value} отключен, событие не опубликовано")
            return False

        try:
            # Определяем тип события
            if isinstance(event, Event):
                event_type = event.event_type
                data = event.data
                source = event.source
                correlation_id = event.correlation_id
            elif isinstance(event, EventType):
                event_type = event.value
            else:
                event_type = event

            await self._unified_bus.publish(
                event_type=event_type,
                data=data,
                source=source,
                correlation_id=correlation_id,
                domain=self.domain
            )
            self._event_count += 1
            return True

        except Exception as e:
            self._error_count += 1
            self._logger.error(f"Ошибка публикации события: {e}")
            return False

    def enable(self):
        """Включение домена."""
        self._enabled = True
        self._logger.info(f"Домен {self.domain.value} включен")

    def disable(self):
        """Выключение домена."""
        self._enabled = False
        self._logger.info(f"Домен {self.domain.value} выключен")

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики по домену."""
        return {
            "domain": self.domain.value,
            "enabled": self._enabled,
            "event_count": self._event_count,
            "error_count": self._error_count,
        }


class EventBusAdapter:
    """
    Адаптер для плавной миграции на UnifiedEventBus.

    Эмулирует старый API EventBusManager для обратной совместимости.

    WARNING: Этот класс будет удалён после завершения миграции!

    FEATURES:
    - Эмуляция get_bus(domain) через DomainEventBusProxy
    - Эмуляция publish() с domain параметром
    - Поддержка subscribe_all() для глобальных подписчиков
    - Логирование вызовов для отслеживания миграции

    USAGE:
    ```python
    # Создание адаптера
    from core.infrastructure.event_bus.unified_event_bus import get_event_bus
    from core.infrastructure.event_bus.event_bus_adapter import EventBusAdapter

    unified_bus = get_event_bus()
    adapter = EventBusAdapter(unified_bus)

    # Старый API работает
    agent_bus = adapter.get_bus(EventDomain.AGENT)
    agent_bus.subscribe(EventType.AGENT_STARTED, handler)
    await agent_bus.publish(EventType.AGENT_STARTED, {"agent_id": "123"})

    # Новый API тоже доступен
    await unified_bus.publish(
        EventType.AGENT_STARTED,
        data={"agent_id": "123"},
        session_id="session_123",
        domain=EventDomain.AGENT
    )
    ```
    """

    def __init__(self, unified_bus: UnifiedEventBus):
        self._unified_bus = unified_bus
        self._proxies: Dict[EventDomain, DomainEventBusProxy] = {}
        self._global_subscribers: List[Callable] = []
        self._logger = logging.getLogger(f"{__name__}.EventBusAdapter")

        # Кэшируем прокси для всех доменов
        for domain in EventDomain:
            self._proxies[domain] = DomainEventBusProxy(unified_bus, domain)

        self._logger.info("EventBusAdapter инициализирован")

    def get_bus(self, domain: Union[EventDomain, str]) -> DomainEventBusProxy:
        """
        Получение шины конкретного домена (эмуляция старого API).

        ARGS:
        - domain: домен (EventDomain или строка)

        RETURNS:
        - DomainEventBusProxy: прокси шины событий домена
        """
        if isinstance(domain, str):
            try:
                domain = EventDomain(domain)
            except ValueError:
                raise ValueError(
                    f"Неизвестный домен: {domain}. "
                    f"Доступные: {[d.value for d in EventDomain]}"
                )

        if domain not in self._proxies:
            raise ValueError(f"Домен {domain.value} не найден")

        return self._proxies[domain]

    async def publish(
        self,
        event: Union[Event, str, EventType],
        data: Dict[str, Any] = None,
        source: str = "",
        correlation_id: str = "",
        domain: Optional[EventDomain] = None
    ) -> bool:
        """
        Публикация события в шину домена (эмуляция старого API).

        ARGS:
        - event: событие для публикации
        - data: данные события
        - source: источник события
        - correlation_id: идентификатор корреляции
        - domain: целевой домен (опционально, определяется автоматически)

        RETURNS:
        - bool: True если событие опубликовано успешно
        """
        # Определение домена
        if domain is None:
            if isinstance(event, Event):
                domain = event.domain if hasattr(event, 'domain') else get_event_domain(event.event_type)
            elif isinstance(event, EventType):
                domain = get_event_domain(event)
            else:
                domain = get_event_domain(event)

        # Публикация через UnifiedEventBus
        if isinstance(event, Event):
            event_type = event.event_type
            data = event.data
            source = event.source
            correlation_id = event.correlation_id
        elif isinstance(event, EventType):
            event_type = event.value
        else:
            event_type = event

        return await self._unified_bus.publish(
            event_type=event_type,
            data=data,
            source=source,
            correlation_id=correlation_id,
            domain=domain
        )

    async def publish_cross_domain(
        self,
        event: Union[Event, str, EventType],
        domains: List[Union[EventDomain, str]],
        data: Dict[str, Any] = None,
        source: str = "",
        correlation_id: str = ""
    ) -> Dict[str, bool]:
        """
        Публикация события в несколько доменов одновременно.

        ARGS:
        - event: событие для публикации
        - domains: список целевых доменов
        - data: данные события
        - source: источник события
        - correlation_id: идентификатор корреляции

        RETURNS:
        - Dict[str, bool]: результат публикации по каждому домену
        """
        results = {}

        for domain in domains:
            try:
                result = await self.publish(event, data, source, correlation_id, domain)
                domain_name = domain.value if isinstance(domain, EventDomain) else domain
                results[domain_name] = result
            except Exception as e:
                domain_name = domain.value if isinstance(domain, EventDomain) else domain
                results[domain_name] = False
                self._logger.error(f"Ошибка публикации в домен {domain_name}: {e}")

        return results

    def subscribe_all(self, handler: Callable):
        """
        Подписка на все события во всех доменах.

        ARGS:
        - handler: обработчик событий
        """
        self._global_subscribers.append(handler)
        self._unified_bus.subscribe_all(handler)
        self._logger.debug("Зарегистрирован глобальный подписчик на все события")

    def on_cross_domain_event(self, event_type: str, handler: Callable):
        """
        Регистрация обработчика на кросс-доменные события.

        ARGS:
        - event_type: тип события для обработки
        - handler: обработчик события
        """
        # В UnifiedEventBus это просто подписка на конкретный event_type
        self._unified_bus.subscribe(event_type, handler)

    def enable_domain(self, domain: Union[EventDomain, str]):
        """Включение домена."""
        bus = self.get_bus(domain)
        bus.enable()

    def disable_domain(self, domain: Union[EventDomain, str]):
        """Выключение домена."""
        bus = self.get_bus(domain)
        bus.disable()

    def get_all_stats(self) -> Dict[str, Any]:
        """Получение статистики по всем доменам."""
        return {
            "domains": {
                domain.value: proxy.get_stats()
                for domain, proxy in self._proxies.items()
            },
            "global_subscribers_count": len(self._global_subscribers),
            "unified_bus_stats": self._unified_bus.get_stats()
        }

    async def shutdown(self):
        """Корректное завершение работы всех шин."""
        self._logger.info("Завершение работы EventBusAdapter")
        for domain, proxy in self._proxies.items():
            proxy.disable()
            self._logger.debug(f"Домен {domain.value} отключен")


# =============================================================================
# GLOBAL SINGLETON (для обратной совместимости)
# =============================================================================

_global_adapter: Optional[EventBusAdapter] = None


def get_event_bus_adapter() -> EventBusAdapter:
    """
    Получение глобального EventBusAdapter (singleton).

    WARNING: Временная функция для обратной совместимости!

    RETURNS:
    - EventBusAdapter: глобальный экземпляр адаптера
    """
    global _global_adapter
    if _global_adapter is None:
        from .unified_event_bus import get_event_bus
        unified_bus = get_event_bus()
        _global_adapter = EventBusAdapter(unified_bus)
    return _global_adapter


def reset_event_bus_adapter():
    """Сброс глобального адаптера (для тестов)."""
    global _global_adapter
    _global_adapter = None
