"""
Тесты для системы доменных шин событий.

TESTS:
- test_domain_isolation: Изоляция событий между доменами
- test_cross_domain_publish: Кросс-доменная публикация
- test_domain_enable_disable: Включение/выключение доменов
- test_global_subscriber: Глобальная подписка на все события
- test_event_domain_mapping: Автоматическое определение домена
- test_domain_stats: Статистика по доменам
- test_singleton: Singleton паттерн для менеджера
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.event_bus import (
    EventBusManager,
    DomainEventBus,
    DomainEvent,
    EventDomain,
    EventType,
    Event,
    get_event_bus_manager,
    reset_event_bus_manager,
    get_event_bus,
)


@pytest.fixture
def event_bus_manager():
    """Фикстура: новый менеджер шин для каждого теста."""
    reset_event_bus_manager()
    manager = EventBusManager()
    yield manager
    reset_event_bus_manager()


@pytest.fixture
def domain_bus(event_bus_manager):
    """Фикстура: шина домена AGENT."""
    return event_bus_manager.get_bus(EventDomain.AGENT)


class TestDomainIsolation:
    """Тесты изоляции доменов."""

    @pytest.mark.asyncio
    async def test_domain_isolation(self, event_bus_manager):
        """События одного домена не попадают в другие домены."""
        agent_events = []
        benchmark_events = []
        infra_events = []

        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
        benchmark_bus = event_bus_manager.get_bus(EventDomain.BENCHMARK)
        infra_bus = event_bus_manager.get_bus(EventDomain.INFRASTRUCTURE)

        # Подписка на события в разных доменах
        agent_bus.subscribe(EventType.AGENT_CREATED, lambda e: agent_events.append(e))
        benchmark_bus.subscribe(
            EventType.BENCHMARK_STARTED, lambda e: benchmark_events.append(e)
        )
        infra_bus.subscribe(EventType.LLM_CALL_STARTED, lambda e: infra_events.append(e))

        # Публикация в разные домены
        await agent_bus.publish(EventType.AGENT_CREATED, data={"agent_id": "1"})
        await benchmark_bus.publish(EventType.BENCHMARK_STARTED, data={"benchmark_id": "1"})
        await infra_bus.publish(EventType.LLM_CALL_STARTED, data={"provider": "llama"})

        # Проверка изоляции
        assert len(agent_events) == 1
        assert len(benchmark_events) == 1
        assert len(infra_events) == 1

        assert agent_events[0].data["agent_id"] == "1"
        assert benchmark_events[0].data["benchmark_id"] == "1"
        assert infra_events[0].data["provider"] == "llama"

    @pytest.mark.asyncio
    async def test_same_domain_events_received(self, event_bus_manager):
        """События одного домена получаются всеми подписчиками."""
        events = []

        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)

        # Несколько подписчиков на один домен
        agent_bus.subscribe(EventType.AGENT_CREATED, lambda e: events.append(("sub1", e)))
        agent_bus.subscribe(EventType.AGENT_CREATED, lambda e: events.append(("sub2", e)))

        await agent_bus.publish(EventType.AGENT_CREATED, data={"test": "data"})

        assert len(events) == 2
        assert events[0][0] == "sub1"
        assert events[1][0] == "sub2"


class TestCrossDomainPublish:
    """Тесты кросс-доменной публикации."""

    @pytest.mark.asyncio
    async def test_publish_cross_domain(self, event_bus_manager):
        """Публикация события в несколько доменов."""
        agent_events = []
        infra_events = []

        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
        infra_bus = event_bus_manager.get_bus(EventDomain.INFRASTRUCTURE)

        agent_bus.subscribe(EventType.SYSTEM_INITIALIZED, lambda e: agent_events.append(e))
        infra_bus.subscribe(EventType.SYSTEM_INITIALIZED, lambda e: infra_events.append(e))

        # Кросс-доменная публикация
        results = await event_bus_manager.publish_cross_domain(
            EventType.SYSTEM_INITIALIZED,
            domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE],
            data={"version": "1.0.0"},
        )

        # Проверка результатов
        assert results["agent"] is True
        assert results["infrastructure"] is True
        assert len(agent_events) == 1
        assert len(infra_events) == 1

    @pytest.mark.asyncio
    async def test_publish_cross_domain_partial_failure(self, event_bus_manager):
        """Кросс-доменная публикация с частичным успехом."""
        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)

        # Отключение домена INFRASTRUCTURE
        event_bus_manager.disable_domain(EventDomain.INFRASTRUCTURE)

        results = await event_bus_manager.publish_cross_domain(
            EventType.SYSTEM_INITIALIZED,
            domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE],
        )

        assert results["agent"] is True
        assert results["infrastructure"] is False


class TestDomainEnableDisable:
    """Тесты включения/выключения доменов."""

    @pytest.mark.asyncio
    async def test_disable_domain(self, domain_bus):
        """Выключенный домен не публикует события."""
        events = []

        domain_bus.subscribe(EventType.AGENT_CREATED, lambda e: events.append(e))
        domain_bus.disable()

        result = await domain_bus.publish(EventType.AGENT_CREATED, data={})

        assert result is False
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_enable_domain(self, domain_bus):
        """Включение домена после выключения."""
        events = []

        domain_bus.subscribe(EventType.AGENT_CREATED, lambda e: events.append(e))
        domain_bus.disable()
        domain_bus.enable()

        result = await domain_bus.publish(EventType.AGENT_CREATED, data={})

        assert result is True
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_domain_stats(self, event_bus_manager):
        """Статистика по домену."""
        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)

        # Публикация нескольких событий
        await agent_bus.publish(EventType.AGENT_CREATED, {})
        await agent_bus.publish(EventType.AGENT_STARTED, {})

        stats = agent_bus.get_stats()

        assert stats["domain"] == "agent"
        assert stats["enabled"] is True
        assert stats["event_count"] == 2
        assert stats["error_count"] == 0


class TestGlobalSubscriber:
    """Тесты глобальной подписки."""

    @pytest.mark.asyncio
    async def test_global_subscriber_receives_all(self, event_bus_manager):
        """Глобальный подписчик получает все события."""
        global_events = []

        async def global_handler(event: DomainEvent):
            global_events.append(event)

        event_bus_manager.subscribe_all(global_handler)

        # Публикация в разные домены
        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
        benchmark_bus = event_bus_manager.get_bus(EventDomain.BENCHMARK)

        await agent_bus.publish(EventType.AGENT_CREATED, {})
        await benchmark_bus.publish(EventType.BENCHMARK_STARTED, {})

        # Даем время на выполнение асинхронных задач
        await asyncio.sleep(0.01)

        # Глобальный подписчик получил оба события
        assert len(global_events) == 2
        assert global_events[0].domain == EventDomain.AGENT
        assert global_events[1].domain == EventDomain.BENCHMARK


class TestEventDomainMapping:
    """Тесты автоматического определения домена."""

    def test_event_type_to_domain_mapping(self):
        """Проверка маппинга типов событий на домены."""
        from core.infrastructure.event_bus.domain_event_bus import EVENT_TYPE_TO_DOMAIN

        # Проверка ключевых маппингов
        assert EVENT_TYPE_TO_DOMAIN[EventType.AGENT_CREATED] == EventDomain.AGENT
        assert EVENT_TYPE_TO_DOMAIN[EventType.BENCHMARK_STARTED] == EventDomain.BENCHMARK
        assert (
            EVENT_TYPE_TO_DOMAIN[EventType.LLM_CALL_STARTED] == EventDomain.INFRASTRUCTURE
        )
        assert EVENT_TYPE_TO_DOMAIN[EventType.VERSION_CREATED] == EventDomain.OPTIMIZATION
        assert EVENT_TYPE_TO_DOMAIN[EventType.ERROR_OCCURRED] == EventDomain.COMMON

    @pytest.mark.asyncio
    async def test_auto_domain_detection(self, event_bus_manager):
        """Автоматическое определение домена по типу события."""
        agent_events = []
        agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
        agent_bus.subscribe(EventType.AGENT_CREATED, lambda e: agent_events.append(e))

        # Публикация без явного указания домена
        await event_bus_manager.publish(EventType.AGENT_CREATED, data={"test": "data"})

        assert len(agent_events) == 1
        assert agent_events[0].domain == EventDomain.AGENT


class TestDomainEventBus:
    """Тесты класса DomainEventBus."""

    @pytest.mark.asyncio
    async def test_domain_event_from_event(self):
        """Создание DomainEvent из Event."""
        event = Event(
            event_type=EventType.AGENT_CREATED.value,
            data={"agent_id": "123"},
            source="test",
        )

        domain_event = DomainEvent.from_event(event, EventDomain.AGENT)

        assert domain_event.domain == EventDomain.AGENT
        assert domain_event.event_type == EventType.AGENT_CREATED.value
        assert domain_event.data == {"agent_id": "123"}
        assert domain_event.source == "test"

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self, domain_bus):
        """Подписка и отписка от событий."""
        events = []
        handler = lambda e: events.append(e)

        domain_bus.subscribe(EventType.AGENT_CREATED, handler)
        await domain_bus.publish(EventType.AGENT_CREATED, {})
        assert len(events) == 1

        # Отписка
        domain_bus.unsubscribe(EventType.AGENT_CREATED, handler)
        await domain_bus.publish(EventType.AGENT_CREATED, {})
        assert len(events) == 1  # Не изменилось


class TestSingleton:
    """Тесты singleton паттерна."""

    def test_get_event_bus_manager_singleton(self):
        """get_event_bus_manager возвращает тот же экземпляр."""
        reset_event_bus_manager()

        manager1 = get_event_bus_manager()
        manager2 = get_event_bus_manager()

        assert manager1 is manager2

    def test_reset_event_bus_manager(self):
        """Сброс singleton для тестов."""
        reset_event_bus_manager()
        manager1 = get_event_bus_manager()

        reset_event_bus_manager()
        manager2 = get_event_bus_manager()

        assert manager1 is not manager2

    def test_get_event_bus_backward_compatibility(self):
        """get_event_bus для обратной совместимости."""
        reset_event_bus_manager()

        # Старый API должен работать
        event_bus = get_event_bus()

        # Возвращает базовую шину COMMON домена
        assert event_bus is not None


class TestErrorHandler:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_error_in_handler_doesnt_break_bus(self, domain_bus):
        """Ошибка в обработчике не ломает шину событий."""
        events = []

        def good_handler(e):
            events.append(e)

        def bad_handler(e):
            raise Exception("Handler error")

        domain_bus.subscribe(EventType.AGENT_CREATED, bad_handler)
        domain_bus.subscribe(EventType.AGENT_CREATED, good_handler)

        # Публикация не должна вызвать исключение
        await domain_bus.publish(EventType.AGENT_CREATED, {})

        # Хороший обработчик должен сработать
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_error_count_in_stats(self, domain_bus):
        """Подсчет ошибок в статистике."""
        def bad_handler(e):
            raise Exception("Handler error")

        domain_bus.subscribe(EventType.AGENT_CREATED, bad_handler)

        await domain_bus.publish(EventType.AGENT_CREATED, {})

        stats = domain_bus.get_stats()
        # Ошибки в обработчиках не считаются ошибками публикации
        assert stats["error_count"] == 0


class TestAsyncHandlers:
    """Тесты асинхронных обработчиков."""

    @pytest.mark.asyncio
    async def test_async_handler(self, domain_bus):
        """Асинхронный обработчик событий."""
        events = []

        async def async_handler(e):
            await asyncio.sleep(0.001)  # Имитация асинхронной работы
            events.append(e)

        domain_bus.subscribe(EventType.AGENT_CREATED, async_handler)
        await domain_bus.publish(EventType.AGENT_CREATED, {"test": "data"})

        assert len(events) == 1
        assert events[0].data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self, domain_bus):
        """Смешанные синхронные и асинхронные обработчики."""
        sync_events = []
        async_events = []

        def sync_handler(e):
            sync_events.append(e)

        async def async_handler(e):
            async_events.append(e)

        domain_bus.subscribe(EventType.AGENT_CREATED, sync_handler)
        domain_bus.subscribe(EventType.AGENT_CREATED, async_handler)

        await domain_bus.publish(EventType.AGENT_CREATED, {})

        assert len(sync_events) == 1
        assert len(async_events) == 1
