"""
Тесты для UnifiedEventBus и миграции.

TESTS:
- test_session_isolation: Изоляция событий между сессиями
- test_domain_routing: Domain routing внутри одной шины
- test_no_event_duplication: События не дублируются
- test_session_filters: Фильтры по session_id
- test_domain_filters: Фильтры по domain
- test_backward_compatibility: Обратная совместимость через адаптер
- test_unified_bus_singleton: Singleton для UnifiedEventBus
- test_unified_bus_stats: Статистика UnifiedEventBus
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.event_bus.unified_event_bus import (
    UnifiedEventBus,
    Event,
    EventType,
    EventDomain,
    get_event_bus,
    create_event_bus,
    shutdown_event_bus,
    get_event_domain,
)
from core.infrastructure.event_bus.event_bus_adapter import (
    EventBusAdapter,
    get_event_bus_adapter,
    reset_event_bus_adapter,
)


@pytest.fixture
async def unified_bus():
    """Фикстура: новая шина для каждого теста."""
    bus = create_event_bus()
    yield bus
    # Очистка после теста
    await bus.shutdown(timeout=5.0)


@pytest.fixture
async def adapter():
    """Фикстура: адаптер для обратной совместимости."""
    reset_event_bus_adapter()
    bus = create_event_bus()
    adapter = EventBusAdapter(bus)
    yield adapter
    await bus.shutdown(timeout=5.0)
    reset_event_bus_adapter()


class TestSessionIsolation:
    """Тесты изоляции сессий."""

    @pytest.mark.asyncio
    async def test_session_isolation(self, unified_bus):
        """События сессии A не видны сессии B."""
        session_a_events = []
        session_b_events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: session_a_events.append(e),
            session_id="session_a"
        )
        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: session_b_events.append(e),
            session_id="session_b"
        )

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_a"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "2"},
            session_id="session_b"
        )

        # Даем время на обработку
        await asyncio.sleep(0.05)

        assert len(session_a_events) == 1
        assert len(session_b_events) == 1
        assert session_a_events[0].data["agent_id"] == "1"
        assert session_b_events[0].data["agent_id"] == "2"

    @pytest.mark.asyncio
    async def test_session_without_filter(self, unified_bus):
        """Подписка без session_id получает все события."""
        all_events = []

        unified_bus.subscribe(EventType.AGENT_STARTED, lambda e: all_events.append(e))

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_a"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "2"},
            session_id="session_b"
        )

        await asyncio.sleep(0.05)

        assert len(all_events) == 2


class TestDomainRouting:
    """Тесты domain routing."""

    @pytest.mark.asyncio
    async def test_domain_routing(self, unified_bus):
        """Domain filter работает корректно."""
        agent_events = []
        infra_events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: agent_events.append(e),
            domain=EventDomain.AGENT
        )
        unified_bus.subscribe(
            EventType.SYSTEM_INITIALIZED,
            lambda e: infra_events.append(e),
            domain=EventDomain.INFRASTRUCTURE
        )

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            domain=EventDomain.AGENT
        )
        await unified_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"version": "1.0"},
            domain=EventDomain.INFRASTRUCTURE
        )

        await asyncio.sleep(0.05)

        assert len(agent_events) == 1
        assert len(infra_events) == 1
        assert agent_events[0].domain == EventDomain.AGENT
        assert infra_events[0].domain == EventDomain.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_domain_filter_prevents_cross_domain(self, unified_bus):
        """Подписчик с domain фильтром не получает события других доменов."""
        agent_events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: agent_events.append(e),
            domain=EventDomain.AGENT
        )

        # Публикация события INFRASTRUCTURE
        await unified_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"version": "1.0"},
            domain=EventDomain.INFRASTRUCTURE
        )

        await asyncio.sleep(0.05)

        # Подписчик на AGENT не должен получить INFRASTRUCTURE событие
        assert len(agent_events) == 0

    @pytest.mark.asyncio
    async def test_subscribe_all_with_domain_filter(self, unified_bus):
        """subscribe_all с фильтром по доменам."""
        all_events = []
        agent_only_events = []

        unified_bus.subscribe_all(lambda e: all_events.append(e))
        unified_bus.subscribe_all(
            lambda e: agent_only_events.append(e),
            domains=[EventDomain.AGENT]
        )

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            domain=EventDomain.AGENT
        )
        await unified_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"version": "1.0"},
            domain=EventDomain.INFRASTRUCTURE
        )

        await asyncio.sleep(0.05)

        # Все события
        assert len(all_events) == 2
        # Только AGENT события
        assert len(agent_only_events) == 1
        assert agent_only_events[0].domain == EventDomain.AGENT


class TestNoEventDuplication:
    """Тесты отсутствия дублирования событий."""

    @pytest.mark.asyncio
    async def test_no_event_duplication(self, unified_bus):
        """Событие не дублируется — критично для миграции!"""
        received_count = 0

        def handler(event):
            nonlocal received_count
            received_count += 1

        unified_bus.subscribe(EventType.AGENT_STARTED, handler)

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        assert received_count == 1, "Событие не должно дублироваться!"

    @pytest.mark.asyncio
    async def test_multiple_handlers_no_duplication(self, unified_bus):
        """Несколько обработчиков — каждый получает по одному событию."""
        handler1_count = 0
        handler2_count = 0

        def handler1(event):
            nonlocal handler1_count
            handler1_count += 1

        def handler2(event):
            nonlocal handler2_count
            handler2_count += 1

        unified_bus.subscribe(EventType.AGENT_STARTED, handler1)
        unified_bus.subscribe(EventType.AGENT_STARTED, handler2)

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        assert handler1_count == 1
        assert handler2_count == 1


class TestSessionFilters:
    """Тесты фильтров по session_id."""

    @pytest.mark.asyncio
    async def test_session_filter_specific_session(self, unified_bus):
        """Подписка на конкретную сессию."""
        session_a_events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: session_a_events.append(e),
            session_id="session_a"
        )

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_a"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "2"},
            session_id="session_b"
        )

        await asyncio.sleep(0.05)

        assert len(session_a_events) == 1
        assert session_a_events[0].data["agent_id"] == "1"

    @pytest.mark.asyncio
    async def test_session_filter_with_domain(self, unified_bus):
        """Комбинированный фильтр: session_id + domain."""
        events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: events.append(e),
            session_id="session_a",
            domain=EventDomain.AGENT
        )

        # Это событие должно пройти
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_a",
            domain=EventDomain.AGENT
        )

        # Это событие не должно пройти (другая сессия)
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "2"},
            session_id="session_b",
            domain=EventDomain.AGENT
        )

        # Это событие не должно пройти (другой домен)
        await unified_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"version": "1.0"},
            session_id="session_a",
            domain=EventDomain.INFRASTRUCTURE
        )

        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["agent_id"] == "1"


class TestDomainFilters:
    """Тесты фильтров по domain."""

    @pytest.mark.asyncio
    async def test_domain_filter_auto_detection(self, unified_bus):
        """Автоматическое определение домена по типу события."""
        events = []

        unified_bus.subscribe(
            EventType.AGENT_STARTED,
            lambda e: events.append(e),
            domain=EventDomain.AGENT
        )

        # Публикация без явного указания домена — должен определиться автоматически
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].domain == EventDomain.AGENT

    def test_get_event_domain(self):
        """Проверка функции get_event_domain."""
        assert get_event_domain(EventType.AGENT_STARTED) == EventDomain.AGENT
        assert get_event_domain(EventType.BENCHMARK_STARTED) == EventDomain.BENCHMARK
        assert get_event_domain(EventType.SYSTEM_INITIALIZED) == EventDomain.INFRASTRUCTURE
        assert get_event_domain(EventType.ERROR_OCCURRED) == EventDomain.COMMON
        assert get_event_domain("unknown.event") == EventDomain.COMMON


class TestBackwardCompatibility:
    """Тесты обратной совместимости через адаптер."""

    @pytest.mark.asyncio
    async def test_adapter_get_bus(self, adapter):
        """Адаптер эмулирует get_bus(domain)."""
        agent_bus = adapter.get_bus(EventDomain.AGENT)
        benchmark_bus = adapter.get_bus(EventDomain.BENCHMARK)

        assert agent_bus is not None
        assert benchmark_bus is not None
        assert agent_bus.domain == EventDomain.AGENT
        assert benchmark_bus.domain == EventDomain.BENCHMARK

    @pytest.mark.asyncio
    async def test_adapter_publish(self, adapter):
        """Адаптер publish работает через UnifiedEventBus."""
        agent_bus = adapter.get_bus(EventDomain.AGENT)
        events = []

        # Подписываемся через adapter
        agent_bus.subscribe(EventType.AGENT_STARTED, lambda e: events.append(e))

        await agent_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"}
        )

        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].domain == EventDomain.AGENT

    @pytest.mark.asyncio
    async def test_adapter_publish_cross_domain(self, adapter):
        """Адаптер publish_cross_domain работает."""
        agent_events = []
        infra_events = []

        agent_bus = adapter.get_bus(EventDomain.AGENT)
        infra_bus = adapter.get_bus(EventDomain.INFRASTRUCTURE)

        agent_bus.subscribe(EventType.SYSTEM_INITIALIZED, lambda e: agent_events.append(e))
        infra_bus.subscribe(EventType.SYSTEM_INITIALIZED, lambda e: infra_events.append(e))

        results = await adapter.publish_cross_domain(
            EventType.SYSTEM_INITIALIZED,
            domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE],
            data={"version": "1.0"},
        )

        await asyncio.sleep(0.05)

        assert results["agent"] is True
        assert results["infrastructure"] is True
        assert len(agent_events) == 1
        assert len(infra_events) == 1

    @pytest.mark.asyncio
    async def test_adapter_enable_disable(self, adapter):
        """Адаптер enable/disable domain работает."""
        events = []

        # Получаем шину и подписываемся
        agent_bus = adapter.get_bus(EventDomain.AGENT)
        agent_bus.subscribe(EventType.AGENT_STARTED, lambda e: events.append(e))

        agent_bus.disable()
        result = await agent_bus.publish(EventType.AGENT_STARTED, data={})
        assert result is False
        await asyncio.sleep(0.05)
        assert len(events) == 0

        agent_bus.enable()
        result = await agent_bus.publish(EventType.AGENT_STARTED, data={})
        assert result is True
        await asyncio.sleep(0.05)
        assert len(events) == 1


class TestUnifiedBusSingleton:
    """Тесты singleton для UnifiedEventBus."""

    def test_get_event_bus_singleton(self):
        """get_event_bus возвращает тот же экземпляр."""
        # Сбрасываем предыдущий singleton
        import core.infrastructure.event_bus.unified_event_bus as module
        module._global_event_bus = None

        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    def test_create_event_bus_new_instance(self):
        """create_event_bus создаёт новый экземпляр для тестов."""
        bus1 = create_event_bus()
        bus2 = create_event_bus()

        assert bus1 is not bus2


class TestUnifiedBusStats:
    """Тесты статистики UnifiedEventBus."""

    @pytest.mark.asyncio
    async def test_get_stats(self, unified_bus):
        """Статистика шины."""
        stats = unified_bus.get_stats()

        assert "running" in stats
        assert "active_sessions" in stats
        assert "active_workers" in stats
        assert "subscribers_count" in stats

        assert stats["running"] is True
        assert stats["active_sessions"] == 0
        assert stats["active_workers"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_publish(self, unified_bus):
        """Статистика после публикации событий."""
        unified_bus.subscribe(EventType.AGENT_STARTED, lambda e: None)

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"agent_id": "1"},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        stats = unified_bus.get_stats()

        assert stats["active_sessions"] == 1
        assert stats["active_workers"] == 1
        assert "session_1" in stats["sessions"]

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, unified_bus):
        """Получение списка активных сессий."""
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            session_id="session_a"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            session_id="session_b"
        )

        await asyncio.sleep(0.05)

        sessions = unified_bus.get_active_sessions()

        assert "session_a" in sessions
        assert "session_b" in sessions

    @pytest.mark.asyncio
    async def test_get_sessions_by_agent(self, unified_bus):
        """Получение сессий по agent_id."""
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            session_id="session_a",
            agent_id="agent_1"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            session_id="session_b",
            agent_id="agent_1"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            session_id="session_c",
            agent_id="agent_2"
        )

        await asyncio.sleep(0.05)

        sessions = unified_bus.get_sessions_by_agent("agent_1")

        assert len(sessions) == 2
        assert "session_a" in sessions
        assert "session_b" in sessions


class TestAsyncHandlers:
    """Тесты асинхронных обработчиков."""

    @pytest.mark.asyncio
    async def test_async_handler(self, unified_bus):
        """Асинхронный обработчик событий."""
        events = []

        async def async_handler(e):
            await asyncio.sleep(0.001)
            events.append(e)

        unified_bus.subscribe(EventType.AGENT_STARTED, async_handler)
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"test": "data"},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self, unified_bus):
        """Смешанные синхронные и асинхронные обработчики."""
        sync_events = []
        async_events = []

        def sync_handler(e):
            sync_events.append(e)

        async def async_handler(e):
            async_events.append(e)

        unified_bus.subscribe(EventType.AGENT_STARTED, sync_handler)
        unified_bus.subscribe(EventType.AGENT_STARTED, async_handler)

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        assert len(sync_events) == 1
        assert len(async_events) == 1


class TestErrorHandler:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_error_in_handler_doesnt_break_bus(self, unified_bus):
        """Ошибка в обработчике не ломает шину событий."""
        events = []

        def good_handler(e):
            events.append(e)

        def bad_handler(e):
            raise Exception("Handler error")

        unified_bus.subscribe(EventType.AGENT_STARTED, bad_handler)
        unified_bus.subscribe(EventType.AGENT_STARTED, good_handler)

        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        # Хороший обработчик должен сработать
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_session_worker_error_recovery(self, unified_bus):
        """Worker восстанавливается после ошибки в обработчике."""
        event_count = 0

        def handler(e):
            nonlocal event_count
            event_count += 1
            if event_count == 1:
                raise Exception("First event error")

        unified_bus.subscribe(EventType.AGENT_STARTED, handler)

        # Первое событие вызовет ошибку, второе должно обработаться
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": 1},
            session_id="session_1"
        )
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": 2},
            session_id="session_1"
        )

        await asyncio.sleep(0.05)

        # Оба события должны быть обработаны
        assert event_count == 2
