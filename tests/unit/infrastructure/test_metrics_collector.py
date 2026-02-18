"""
Юнит-тесты для MetricsCollector.

ТЕСТЫ:
- test_metrics_collector_initialization: инициализация и подписки
- test_on_skill_executed_records_metric: запись метрик выполнения
- test_on_capability_selected_records_metric: запись выбора способности
- test_on_error_occurred_records_metric: запись ошибок
- test_get_aggregated_metrics: получение агрегированных метрик
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
from core.infrastructure.metrics_collector import MetricsCollector


class MockMetricsStorage:
    """Моковое хранилище метрик для тестов"""

    def __init__(self):
        self.records = []
        self.aggregated = None

    async def record(self, metric: MetricRecord) -> None:
        self.records.append(metric)

    async def get_records(
        self,
        capability: str,
        version: str = None,
        time_range: tuple = None,
        limit: int = None
    ) -> list:
        result = [r for r in self.records if r.capability == capability]
        if version:
            result = [r for r in result if r.version == version]
        if limit:
            result = result[:limit]
        return result

    async def aggregate(
        self,
        capability: str,
        version: str,
        time_range: tuple = None
    ) -> AggregatedMetrics:
        records = await self.get_records(capability, version)
        return AggregatedMetrics.from_records(capability, version, records)

    async def clear_old(self, older_than: datetime) -> int:
        return 0


@pytest.fixture
def event_bus():
    """Фикстура EventBus"""
    return EventBus()


@pytest.fixture
def storage():
    """Фикстура хранилища"""
    return MockMetricsStorage()


@pytest.fixture
def collector(event_bus, storage):
    """Фикстура MetricsCollector"""
    return MetricsCollector(event_bus, storage)


class TestMetricsCollectorInitialization:
    """Тесты инициализации MetricsCollector"""

    @pytest.mark.asyncio
    async def test_metrics_collector_initialization(self, collector):
        """Тест инициализации сборщика метрик"""
        assert collector.is_initialized is False
        assert collector.subscriptions_count == 0

        # Инициализация
        await collector.initialize()

        assert collector.is_initialized is True
        assert collector.subscriptions_count == 4  # 4 типа событий

    @pytest.mark.asyncio
    async def test_double_initialization(self, collector):
        """Тест повторной инициализации"""
        await collector.initialize()
        initial_count = collector.subscriptions_count

        # Повторная инициализация
        await collector.initialize()

        # Количество подписок не должно измениться
        assert collector.subscriptions_count == initial_count

    @pytest.mark.asyncio
    async def test_shutdown(self, collector):
        """Тест завершения работы"""
        await collector.initialize()
        assert collector.is_initialized is True

        await collector.shutdown()

        assert collector.is_initialized is False


class TestSkillExecutedHandler:
    """Тесты обработчика SKILL_EXECUTED"""

    @pytest.mark.asyncio
    async def test_on_skill_executed_records_metric(self, collector, storage, event_bus):
        """Тест записи метрик при выполнении навыка"""
        await collector.initialize()

        # Публикация события
        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'success': True,
                'execution_time_ms': 150.5,
                'tokens_used': 500,
                'version': 'v1.0',
                'session_id': 'session_123'
            },
            correlation_id='corr_456'
        )

        # Небольшая задержка для обработки
        import asyncio
        await asyncio.sleep(0.01)

        # Проверка записанных метрик
        assert len(storage.records) >= 1

        # Проверка метрики успешности
        success_metrics = [r for r in storage.records if r.name == 'success']
        assert len(success_metrics) >= 1
        assert success_metrics[0].value == 1.0
        assert success_metrics[0].capability == 'test_capability'
        assert success_metrics[0].version == 'v1.0'

    @pytest.mark.asyncio
    async def test_on_skill_executed_failure(self, collector, storage, event_bus):
        """Тест записи метрики неудачи"""
        await collector.initialize()

        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'success': False,
                'execution_time_ms': 100.0,
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка метрики неудачи
        success_metrics = [r for r in storage.records if r.name == 'success']
        assert len(success_metrics) >= 1
        assert success_metrics[0].value == 0.0

    @pytest.mark.asyncio
    async def test_on_skill_executed_without_capability(self, collector, storage, event_bus):
        """Тест пропуска события без capability"""
        await collector.initialize()

        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'success': True
                # capability отсутствует
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Метрики не должны быть записаны
        assert len(storage.records) == 0

    @pytest.mark.asyncio
    async def test_on_skill_executed_all_metrics(self, collector, storage, event_bus):
        """Тест записи всех типов метрик"""
        await collector.initialize()

        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_cap',
                'success': True,
                'execution_time_ms': 200.0,
                'tokens_used': 600,
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка всех типов метрик
        metric_names = [r.name for r in storage.records]
        assert 'success' in metric_names
        assert 'execution_time_ms' in metric_names
        assert 'tokens_used' in metric_names


class TestCapabilitySelectedHandler:
    """Тесты обработчика CAPABILITY_SELECTED"""

    @pytest.mark.asyncio
    async def test_on_capability_selected_records_metric(self, collector, storage, event_bus):
        """Тест записи метрики выбора способности"""
        await collector.initialize()

        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'pattern_id': 'pattern_123',
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка метрики выбора
        selection_metrics = [r for r in storage.records if r.name == 'selection_count']
        assert len(selection_metrics) >= 1
        assert selection_metrics[0].value == 1.0
        assert selection_metrics[0].capability == 'test_capability'

    @pytest.mark.asyncio
    async def test_on_capability_selected_multiple(self, collector, storage, event_bus):
        """Тест множественных выборов способности"""
        await collector.initialize()

        # 3 выбора одной способности
        for i in range(3):
            await event_bus.publish(
                EventType.CAPABILITY_SELECTED,
                data={
                    'agent_id': 'agent_1',
                    'capability': 'test_capability',
                    'version': 'v1.0'
                }
            )

        import asyncio
        await asyncio.sleep(0.01)

        selection_metrics = [r for r in storage.records if r.name == 'selection_count']
        assert len(selection_metrics) == 3


class TestErrorHandler:
    """Тесты обработчика ERROR_OCCURRED"""

    @pytest.mark.asyncio
    async def test_on_error_occurred_records_metric(self, collector, storage, event_bus):
        """Тест записи метрики ошибки"""
        await collector.initialize()

        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'error_type': 'ValidationError',
                'error_message': 'Invalid input',
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка метрики ошибки
        success_metrics = [r for r in storage.records if r.name == 'success']
        assert len(success_metrics) >= 1
        assert success_metrics[0].value == 0.0

        # Проверка счётчика ошибок
        error_metrics = [r for r in storage.records if r.name == 'error_count']
        assert len(error_metrics) >= 1
        assert error_metrics[0].value == 1.0

    @pytest.mark.asyncio
    async def test_on_error_with_tags(self, collector, storage, event_bus):
        """Тест записи ошибки с тегами"""
        await collector.initialize()

        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'error_type': 'TimeoutError',
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        error_metrics = [r for r in storage.records if r.name == 'error_count']
        assert len(error_metrics) >= 1
        assert error_metrics[0].tags.get('error') == 'TimeoutError'


class TestMetricCollectedHandler:
    """Тесты обработчика METRIC_COLLECTED"""

    @pytest.mark.asyncio
    async def test_on_metric_collected(self, collector, storage, event_bus):
        """Тест записи произвольной метрики"""
        await collector.initialize()

        await event_bus.publish(
            EventType.METRIC_COLLECTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_capability',
                'metric_type': 'gauge',
                'name': 'custom_metric',
                'value': 42.5,
                'version': 'v1.0',
                'tags': {'source': 'test'}
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        custom_metrics = [r for r in storage.records if r.name == 'custom_metric']
        assert len(custom_metrics) >= 1
        assert custom_metrics[0].value == 42.5
        assert custom_metrics[0].tags.get('source') == 'test'


class TestGetAggregatedMetrics:
    """Тесты получения агрегированных метрик"""

    @pytest.mark.asyncio
    async def test_get_aggregated_metrics(self, collector, storage):
        """Тест получения агрегированных метрик"""
        # Добавление тестовых метрик
        from core.models.data.metrics import MetricRecord, MetricType

        storage.records = [
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=0.0,
                version='v1.0'
            ),
        ]

        aggregated = await collector.get_aggregated_metrics('test_cap', 'v1.0')

        assert aggregated.capability == 'test_cap'
        assert aggregated.version == 'v1.0'
        assert aggregated.total_runs == 3
        assert aggregated.success_count == 2
        assert aggregated.accuracy == pytest.approx(2/3, rel=1e-5)

    @pytest.mark.asyncio
    async def test_get_metrics(self, collector, storage):
        """Тест получения сырых метрик"""
        from core.models.data.metrics import MetricRecord, MetricType

        storage.records = [
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=0.0,
                version='v1.0'
            ),
        ]

        metrics = await collector.get_metrics('test_cap', 'v1.0')

        assert len(metrics) == 2

    @pytest.mark.asyncio
    async def test_get_metrics_with_limit(self, collector, storage):
        """Тест ограничения количества метрик"""
        from core.models.data.metrics import MetricRecord, MetricType

        for i in range(10):
            storage.records.append(
                MetricRecord(
                    agent_id='agent_1',
                    capability='test_cap',
                    metric_type=MetricType.GAUGE,
                    name='success',
                    value=1.0,
                    version='v1.0'
                )
            )

        metrics = await collector.get_metrics('test_cap', 'v1.0', limit=5)

        assert len(metrics) == 5


class TestEndToEnd:
    """Сквозные тесты MetricsCollector"""

    @pytest.mark.asyncio
    async def test_full_metric_collection_flow(self, collector, storage, event_bus):
        """Тест полного потока сбора метрик"""
        await collector.initialize()

        # Симуляция выполнения навыка
        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'planning.create_plan',
                'success': True,
                'execution_time_ms': 250.0,
                'tokens_used': 800,
                'version': 'v2.0',
                'session_id': 'session_abc'
            },
            correlation_id='corr_xyz'
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка всех записанных метрик
        records = await collector.get_metrics('planning.create_plan', 'v2.0')

        # Должны быть записаны метрики success, execution_time_ms, tokens_used
        metric_names = set(r.name for r in records)
        assert 'success' in metric_names
        assert 'execution_time_ms' in metric_names
        assert 'tokens_used' in metric_names

        # Проверка значений
        success_record = next(r for r in records if r.name == 'success')
        assert success_record.value == 1.0
        assert success_record.session_id == 'session_abc'
        assert success_record.correlation_id == 'corr_xyz'

    @pytest.mark.asyncio
    async def test_multiple_agents_isolation(self, collector, storage, event_bus):
        """Тест изоляции метрик разных агентов"""
        await collector.initialize()

        # Метрики от agent_1
        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_1',
                'capability': 'test_cap',
                'success': True,
                'version': 'v1.0'
            }
        )

        # Метрики от agent_2
        await event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': 'agent_2',
                'capability': 'test_cap',
                'success': False,
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Получение метрик по agent_id
        agent1_records = [r for r in storage.records if r.agent_id == 'agent_1']
        agent2_records = [r for r in storage.records if r.agent_id == 'agent_2']

        assert len(agent1_records) >= 1
        assert len(agent2_records) >= 1

        # Проверка значений
        agent1_success = next(r for r in agent1_records if r.name == 'success')
        agent2_success = next(r for r in agent2_records if r.name == 'success')

        assert agent1_success.value == 1.0
        assert agent2_success.value == 0.0
