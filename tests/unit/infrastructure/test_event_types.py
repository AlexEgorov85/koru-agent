"""
Юнит-тесты для новых EventType в EventBus.

ТЕСТЫ:
- test_new_event_types_exist: проверка существования новых типов событий
- test_event_type_values: проверка значений новых EventType
- test_event_bus_with_new_event_types: тестирование шины событий с новыми типами
"""
import pytest
import asyncio
from core.infrastructure.event_bus.event_bus import EventBus, EventType, Event


class TestNewEventTypes:
    """Тесты для новых EventType"""

    def test_benchmark_event_types_exist(self):
        """Тест существования событий бенчмарков"""
        assert hasattr(EventType, 'BENCHMARK_STARTED')
        assert hasattr(EventType, 'BENCHMARK_COMPLETED')
        assert hasattr(EventType, 'BENCHMARK_FAILED')

    def test_optimization_event_types_exist(self):
        """Тест существования событий оптимизации"""
        assert hasattr(EventType, 'OPTIMIZATION_CYCLE_STARTED')
        assert hasattr(EventType, 'OPTIMIZATION_CYCLE_COMPLETED')
        assert hasattr(EventType, 'OPTIMIZATION_FAILED')

    def test_version_event_types_exist(self):
        """Тест существования событий версий"""
        assert hasattr(EventType, 'VERSION_PROMOTED')
        assert hasattr(EventType, 'VERSION_REJECTED')
        assert hasattr(EventType, 'VERSION_CREATED')

    def test_event_type_values(self):
        """Тест значений новых EventType"""
        # Бенчмарки
        assert EventType.BENCHMARK_STARTED.value == "benchmark.started"
        assert EventType.BENCHMARK_COMPLETED.value == "benchmark.completed"
        assert EventType.BENCHMARK_FAILED.value == "benchmark.failed"

        # Оптимизация
        assert EventType.OPTIMIZATION_CYCLE_STARTED.value == "optimization.cycle.started"
        assert EventType.OPTIMIZATION_CYCLE_COMPLETED.value == "optimization.cycle.completed"
        assert EventType.OPTIMIZATION_FAILED.value == "optimization.failed"

        # Версии
        assert EventType.VERSION_PROMOTED.value == "version.promoted"
        assert EventType.VERSION_REJECTED.value == "version.rejected"
        assert EventType.VERSION_CREATED.value == "version.created"

    def test_event_type_from_string(self):
        """Тест создания EventType из строки"""
        # Бенчмарки
        assert EventType("benchmark.started") == EventType.BENCHMARK_STARTED
        assert EventType("benchmark.completed") == EventType.BENCHMARK_COMPLETED
        assert EventType("benchmark.failed") == EventType.BENCHMARK_FAILED

        # Оптимизация
        assert EventType("optimization.cycle.started") == EventType.OPTIMIZATION_CYCLE_STARTED
        assert EventType("optimization.cycle.completed") == EventType.OPTIMIZATION_CYCLE_COMPLETED
        assert EventType("optimization.failed") == EventType.OPTIMIZATION_FAILED

        # Версии
        assert EventType("version.promoted") == EventType.VERSION_PROMOTED
        assert EventType("version.rejected") == EventType.VERSION_REJECTED
        assert EventType("version.created") == EventType.VERSION_CREATED

    def test_all_event_types_are_unique(self):
        """Тест уникальности всех значений EventType"""
        all_values = [e.value for e in EventType]
        unique_values = set(all_values)
        
        # Все значения должны быть уникальны
        assert len(all_values) == len(unique_values)


class TestEventBusWithNewEventTypes:
    """Тесты EventBus с новыми EventType"""

    @pytest.mark.asyncio
    async def test_benchmark_started_event(self):
        """Тест события BENCHMARK_STARTED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.BENCHMARK_STARTED, handler)

        # Публикация события
        await event_bus.publish(
            EventType.BENCHMARK_STARTED,
            data={
                'scenario_id': 'test_001',
                'capability': 'test_cap',
                'version': 'v1.0'
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].event_type == 'benchmark.started'
        assert received_events[0].data['scenario_id'] == 'test_001'

    @pytest.mark.asyncio
    async def test_benchmark_completed_event(self):
        """Тест события BENCHMARK_COMPLETED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.BENCHMARK_COMPLETED, handler)

        await event_bus.publish(
            EventType.BENCHMARK_COMPLETED,
            data={
                'scenario_id': 'test_001',
                'success': True,
                'overall_score': 0.85
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].data['success'] is True
        assert received_events[0].data['overall_score'] == 0.85

    @pytest.mark.asyncio
    async def test_optimization_cycle_started_event(self):
        """Тест события OPTIMIZATION_CYCLE_STARTED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, handler)

        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_STARTED,
            data={
                'capability': 'test_cap',
                'mode': 'accuracy',
                'target_accuracy': 0.95
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].event_type == 'optimization.cycle.started'
        assert received_events[0].data['mode'] == 'accuracy'

    @pytest.mark.asyncio
    async def test_optimization_cycle_completed_event(self):
        """Тест события OPTIMIZATION_CYCLE_COMPLETED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, handler)

        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            data={
                'capability': 'test_cap',
                'from_version': 'v1.0',
                'to_version': 'v2.0',
                'improvement': 12.5
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].data['improvement'] == 12.5

    @pytest.mark.asyncio
    async def test_version_promoted_event(self):
        """Тест события VERSION_PROMOTED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.VERSION_PROMOTED, handler)

        await event_bus.publish(
            EventType.VERSION_PROMOTED,
            data={
                'capability': 'test_cap',
                'from_version': 'v1.0',
                'to_version': 'v2.0',
                'reason': 'Better accuracy'
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].event_type == 'version.promoted'
        assert received_events[0].data['to_version'] == 'v2.0'

    @pytest.mark.asyncio
    async def test_version_rejected_event(self):
        """Тест события VERSION_REJECTED"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe(EventType.VERSION_REJECTED, handler)

        await event_bus.publish(
            EventType.VERSION_REJECTED,
            data={
                'capability': 'test_cap',
                'version': 'v2.0',
                'reason': 'Lower accuracy'
            },
            source='test'
        )

        assert len(received_events) == 1
        assert received_events[0].data['reason'] == 'Lower accuracy'

    @pytest.mark.asyncio
    async def test_multiple_event_types(self):
        """Тест множественных типов событий"""
        event_bus = EventBus()
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Подписка на несколько событий
        event_bus.subscribe(EventType.BENCHMARK_STARTED, handler)
        event_bus.subscribe(EventType.BENCHMARK_COMPLETED, handler)
        event_bus.subscribe(EventType.VERSION_PROMOTED, handler)

        # Публикация разных событий
        await event_bus.publish(EventType.BENCHMARK_STARTED, data={'step': 1})
        await event_bus.publish(EventType.BENCHMARK_COMPLETED, data={'step': 2})
        await event_bus.publish(EventType.VERSION_PROMOTED, data={'step': 3})

        assert len(received_events) == 3
        assert received_events[0].event_type == 'benchmark.started'
        assert received_events[1].event_type == 'benchmark.completed'
        assert received_events[2].event_type == 'version.promoted'

    @pytest.mark.asyncio
    async def test_all_benchmark_events_flow(self):
        """Тест полного потока событий бенчмарка"""
        event_bus = EventBus()
        events_log = []

        async def handler(event: Event):
            events_log.append(event.event_type)

        # Подписка на все события бенчмарка
        event_bus.subscribe(EventType.BENCHMARK_STARTED, handler)
        event_bus.subscribe(EventType.BENCHMARK_COMPLETED, handler)
        event_bus.subscribe(EventType.BENCHMARK_FAILED, handler)

        # Симуляция потока бенчмарка
        await event_bus.publish(
            EventType.BENCHMARK_STARTED,
            data={'scenario_id': 'test_001'}
        )
        await event_bus.publish(
            EventType.BENCHMARK_COMPLETED,
            data={'scenario_id': 'test_001', 'success': True}
        )

        assert events_log == ['benchmark.started', 'benchmark.completed']

    @pytest.mark.asyncio
    async def test_all_optimization_events_flow(self):
        """Тест полного потока событий оптимизации"""
        event_bus = EventBus()
        events_log = []

        async def handler(event: Event):
            events_log.append(event.event_type)

        # Подписка на все события оптимизации
        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, handler)
        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, handler)
        event_bus.subscribe(EventType.OPTIMIZATION_FAILED, handler)
        event_bus.subscribe(EventType.VERSION_PROMOTED, handler)

        # Симуляция потока оптимизации
        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_STARTED,
            data={'capability': 'test_cap'}
        )
        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            data={'capability': 'test_cap', 'iterations': 5}
        )
        await event_bus.publish(
            EventType.VERSION_PROMOTED,
            data={'capability': 'test_cap', 'to_version': 'v2.0'}
        )

        assert events_log == [
            'optimization.cycle.started',
            'optimization.cycle.completed',
            'version.promoted'
        ]


class TestEventCreation:
    """Тесты создания событий с новыми типами"""

    def test_event_with_benchmark_type(self):
        """Тест создания события с типом бенчмарка"""
        event = Event(
            event_type=EventType.BENCHMARK_STARTED.value,
            data={'scenario_id': 'test_001'},
            source='benchmark_service'
        )

        assert event.event_type == 'benchmark.started'
        assert event.data['scenario_id'] == 'test_001'
        assert event.source == 'benchmark_service'

    def test_event_with_optimization_type(self):
        """Тест создания события с типом оптимизации"""
        event = Event(
            event_type=EventType.OPTIMIZATION_CYCLE_STARTED.value,
            data={'capability': 'test_cap'},
            source='optimization_service'
        )

        assert event.event_type == 'optimization.cycle.started'
        assert event.source == 'optimization_service'

    def test_event_with_version_type(self):
        """Тест создания события с типом версии"""
        event = Event(
            event_type=EventType.VERSION_PROMOTED.value,
            data={'capability': 'test_cap', 'to_version': 'v2.0'},
            source='registry'
        )

        assert event.event_type == 'version.promoted'
        assert event.data['to_version'] == 'v2.0'
