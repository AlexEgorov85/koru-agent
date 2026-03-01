"""
Базовый класс для сборщиков событий через EventBus.

КОМПОНЕНТЫ:
- BaseEventCollector: базовый класс с общей логикой подписки на события

FEATURES:
- Автоматическая подписка на события
- Управление жизненным циклом (initialize/shutdown)
- Логирование подписок
- Хранение списка подписок
"""
import logging
from abc import ABC
from typing import List, Callable, Any

from core.infrastructure.event_bus.unified_logger import EventBusLogger
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType

logger = logging.getLogger(__name__)


class BaseEventCollector(ABC):
    """
    Базовый класс для сборщиков событий через EventBus.

    RESPONSIBILITIES:
    - Подписка на события через EventBus
    - Управление жизненным циклом (initialize/shutdown)
    - Хранение списка подписок

    USAGE:
        class MyCollector(BaseEventCollector):
            async def initialize(self) -> None:
                await super().initialize()
                self._subscribe(EventType.MY_EVENT, self._on_my_event)

            async def _on_my_event(self, event: Event) -> None:
                # Обработка события
                pass
    """

    def __init__(self, event_bus: EventBus, component_name: str = "BaseEventCollector"):
        """
        Инициализация сборщика событий.

        ARGS:
        - event_bus: шина событий для подписки
        - component_name: имя компонента для логирования
        """
        self.event_bus = event_bus
        self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component=component_name)
        self._initialized = False
        self._subscriptions: List[EventType] = []

    async def initialize(self) -> None:
        """
        Инициализация сборщика событий.

        ДОЛЖЕН БЫТЬ ПЕРЕОПРЕДЕЛЁН в наследниках для подписки на конкретные события.
        """
        if self._initialized:
            await self.event_bus_logger.warning("%s уже инициализирован", self.__class__.__name__)
            return

        self._initialized = True
        await self.event_bus_logger.info(
            "%s инициализирован: подписан на %d событий",
            self.__class__.__name__,
            len(self._subscriptions)
        )

    def _subscribe(self, event_type: EventType, handler: Callable[[Event], Any]) -> None:
        """
        Подписка на событие.

        ARGS:
        - event_type: тип события для подписки
        - handler: функция-обработчик события
        """
        self.event_bus.subscribe(event_type, handler)
        self._subscriptions.append(event_type)
        # logger.debug("%s подписан на %s", self.__class__.__name__, event_type.value)

    async def shutdown(self) -> None:
        """
        Корректное завершение работы.

        Отписка от всех событий (если поддерживается EventBus).
        """
        if not self._initialized:
            return

        # Отписка (если метод unsubscribe доступен в EventBus)
        for event_type in self._subscriptions:
            try:
                # Пытаемся отписаться, если метод существует
                if hasattr(self.event_bus, 'unsubscribe'):
                    self.event_bus.unsubscribe(event_type)
            except Exception:
                pass

        self._subscriptions.clear()
        self._initialized = False
        self.event_bus_logger.info("%s завершил работу", self.__class__.__name__)

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self._initialized

    @property
    def subscriptions_count(self) -> int:
        """Количество подписок"""
        return len(self._subscriptions)
