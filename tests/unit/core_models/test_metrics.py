"""
Юнит-тесты для моделей метрик.

ТЕСТЫ:
- test_metric_record_creation: создание MetricRecord
- test_metric_record_serialization: сериализация/десериализация
- test_aggregated_metrics_calculation: расчёт агрегированных метрик
- test_is_better_than: сравнение метрик
"""
import pytest
from datetime import datetime, timedelta
from core.models.data.metrics import MetricType, MetricRecord, AggregatedMetrics


class TestMetricRecord:
    """Тесты для MetricRecord"""

    def test_metric_record_creation(self):
        """Тест создания MetricRecord"""
        record = MetricRecord(
            agent_id='agent_1',
            capability='test_capability',
            metric_type=MetricType.GAUGE,
            name='accuracy',
            value=0.95,
            session_id='session_123',
            correlation_id='corr_456',
            version='v1.0',
            tags={'env': 'test'}
        )

        assert record.agent_id == 'agent_1'
        assert record.capability == 'test_capability'
        assert record.metric_type == MetricType.GAUGE
        assert record.name == 'accuracy'
        assert record.value == 0.95
        assert record.session_id == 'session_123'
        assert record.correlation_id == 'corr_456'
        assert record.version == 'v1.0'
        assert record.tags == {'env': 'test'}
        assert isinstance(record.timestamp, datetime)

    def test_metric_record_default_values(self):
        """Тест значений по умолчанию"""
        record = MetricRecord(
            agent_id='agent_1',
            capability='test_capability',
            metric_type=MetricType.COUNTER,
            name='execution_count',
            value=10
        )

        assert record.session_id is None
        assert record.correlation_id is None
        assert record.version is None
        assert record.tags == {}
        assert isinstance(record.timestamp, datetime)

    def test_metric_record_to_dict(self):
        """Тест сериализации в словарь"""
        timestamp = datetime(2026, 2, 18, 10, 30, 0)
        record = MetricRecord(
            agent_id='agent_1',
            capability='test_capability',
            metric_type=MetricType.GAUGE,
            name='accuracy',
            value=0.95,
            timestamp=timestamp,
            version='v1.0'
        )

        data = record.to_dict()

        assert data['agent_id'] == 'agent_1'
        assert data['capability'] == 'test_capability'
        assert data['metric_type'] == 'gauge'
        assert data['name'] == 'accuracy'
        assert data['value'] == 0.95
        assert data['timestamp'] == '2026-02-18T10:30:00'
        assert data['version'] == 'v1.0'

    def test_metric_record_from_dict(self):
        """Тест десериализации из словаря"""
        data = {
            'agent_id': 'agent_1',
            'capability': 'test_capability',
            'metric_type': 'gauge',
            'name': 'accuracy',
            'value': 0.95,
            'timestamp': '2026-02-18T10:30:00',
            'session_id': 'session_123',
            'correlation_id': 'corr_456',
            'version': 'v1.0',
            'tags': {'env': 'test'}
        }

        record = MetricRecord.from_dict(data)

        assert record.agent_id == 'agent_1'
        assert record.capability == 'test_capability'
        assert record.metric_type == MetricType.GAUGE
        assert record.name == 'accuracy'
        assert record.value == 0.95
        assert record.timestamp == datetime(2026, 2, 18, 10, 30, 0)
        assert record.session_id == 'session_123'
        assert record.correlation_id == 'corr_456'
        assert record.version == 'v1.0'
        assert record.tags == {'env': 'test'}

    def test_metric_record_roundtrip(self):
        """Тест круговой сериализации"""
        original = MetricRecord(
            agent_id='agent_1',
            capability='test_capability',
            metric_type=MetricType.HISTOGRAM,
            name='execution_time_ms',
            value=150.5,
            session_id='session_123',
            version='v2.0',
            tags={'priority': 'high'}
        )

        data = original.to_dict()
        restored = MetricRecord.from_dict(data)

        assert restored.agent_id == original.agent_id
        assert restored.capability == original.capability
        assert restored.metric_type == original.metric_type
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.session_id == original.session_id
        assert restored.version == original.version
        assert restored.tags == original.tags


class TestAggregatedMetrics:
    """Тесты для AggregatedMetrics"""

    def test_aggregated_metrics_empty_records(self):
        """Тест с пустым списком записей"""
        aggregated = AggregatedMetrics.from_records(
            capability='test_capability',
            version='v1.0',
            records=[]
        )

        assert aggregated.capability == 'test_capability'
        assert aggregated.version == 'v1.0'
        assert aggregated.total_runs == 0
        assert aggregated.accuracy == 0.0
        assert aggregated.avg_execution_time_ms == 0.0

    def test_aggregated_metrics_calculation(self):
        """Тест расчёта агрегированных метрик"""
        base_time = datetime(2026, 2, 18, 10, 0, 0)

        records = [
            # Успешное выполнение 1
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=100.0,
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='tokens_used',
                value=500,
                timestamp=base_time
            ),
            # Успешное выполнение 2
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                timestamp=base_time + timedelta(minutes=1)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=150.0,
                timestamp=base_time + timedelta(minutes=1)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='tokens_used',
                value=600,
                timestamp=base_time + timedelta(minutes=1)
            ),
            # Неудачное выполнение
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='success',
                value=0.0,
                timestamp=base_time + timedelta(minutes=2)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=200.0,
                timestamp=base_time + timedelta(minutes=2)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='tokens_used',
                value=400,
                timestamp=base_time + timedelta(minutes=2)
            ),
        ]

        aggregated = AggregatedMetrics.from_records(
            capability='test_capability',
            version='v1.0',
            records=records
        )

        # Проверка подсчётов
        assert aggregated.total_runs == 3
        assert aggregated.success_count == 2
        assert aggregated.failure_count == 1
        assert aggregated.accuracy == pytest.approx(2/3, rel=1e-5)

        # Проверка времени выполнения
        assert aggregated.avg_execution_time_ms == pytest.approx(150.0)
        assert aggregated.min_execution_time_ms == 100.0
        assert aggregated.max_execution_time_ms == 200.0

        # Проверка токенов
        assert aggregated.total_tokens == 1500
        assert aggregated.avg_tokens == pytest.approx(500.0)

        # Проверка временного диапазона
        assert aggregated.time_range[0] == base_time
        assert aggregated.time_range[1] == base_time + timedelta(minutes=2)

    def test_aggregated_metrics_with_custom_metrics(self):
        """Тест с пользовательскими метриками"""
        base_time = datetime(2026, 2, 18, 10, 0, 0)

        records = [
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='user_satisfaction',
                value=4.5,
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_capability',
                metric_type=MetricType.GAUGE,
                name='user_satisfaction',
                value=3.5,
                timestamp=base_time + timedelta(minutes=1)
            ),
        ]

        aggregated = AggregatedMetrics.from_records(
            capability='test_capability',
            version='v1.0',
            records=records
        )

        assert 'user_satisfaction' in aggregated.custom_metrics
        assert aggregated.custom_metrics['user_satisfaction'] == pytest.approx(4.0)

    def test_is_better_than_accuracy(self):
        """Тест сравнения по accuracy"""
        metrics_a = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            accuracy=0.95
        )
        metrics_b = AggregatedMetrics(
            capability='test_capability',
            version='v2.0',
            accuracy=0.85
        )

        assert metrics_a.is_better_than(metrics_b, 'accuracy') is True
        assert metrics_b.is_better_than(metrics_a, 'accuracy') is False

    def test_is_better_than_execution_time(self):
        """Тест сравнения по времени выполнения (меньше = лучше)"""
        metrics_a = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            avg_execution_time_ms=100.0
        )
        metrics_b = AggregatedMetrics(
            capability='test_capability',
            version='v2.0',
            avg_execution_time_ms=150.0
        )

        # Меньше время = лучше
        assert metrics_a.is_better_than(metrics_b, 'avg_execution_time_ms') is True
        assert metrics_b.is_better_than(metrics_a, 'avg_execution_time_ms') is False

    def test_is_better_than_tokens(self):
        """Тест сравнения по токенам (меньше = лучше)"""
        metrics_a = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            avg_tokens=400.0
        )
        metrics_b = AggregatedMetrics(
            capability='test_capability',
            version='v2.0',
            avg_tokens=600.0
        )

        assert metrics_a.is_better_than(metrics_b, 'avg_tokens') is True
        assert metrics_b.is_better_than(metrics_a, 'avg_tokens') is False

    def test_is_better_than_custom_metric(self):
        """Тест сравнения по пользовательской метрике"""
        metrics_a = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            custom_metrics={'user_satisfaction': 4.5}
        )
        metrics_b = AggregatedMetrics(
            capability='test_capability',
            version='v2.0',
            custom_metrics={'user_satisfaction': 3.5}
        )

        assert metrics_a.is_better_than(metrics_b, 'user_satisfaction') is True
        assert metrics_b.is_better_than(metrics_a, 'user_satisfaction') is False

    def test_is_better_than_default(self):
        """Тест сравнения по умолчанию (accuracy)"""
        metrics_a = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            accuracy=0.90
        )
        metrics_b = AggregatedMetrics(
            capability='test_capability',
            version='v2.0',
            accuracy=0.80
        )

        # По умолчанию сравниваем accuracy
        assert metrics_a.is_better_than(metrics_b) is True

    def test_aggregated_metrics_to_dict(self):
        """Тест сериализации AggregatedMetrics"""
        base_time = datetime(2026, 2, 18, 10, 0, 0)
        metrics = AggregatedMetrics(
            capability='test_capability',
            version='v1.0',
            total_runs=10,
            success_count=8,
            accuracy=0.8,
            avg_execution_time_ms=150.0,
            custom_metrics={'user_satisfaction': 4.5},
            time_range=(base_time, base_time + timedelta(hours=1))
        )

        data = metrics.to_dict()

        assert data['capability'] == 'test_capability'
        assert data['version'] == 'v1.0'
        assert data['total_runs'] == 10
        assert data['accuracy'] == 0.8
        assert data['avg_execution_time_ms'] == 150.0
        assert data['custom_metrics'] == {'user_satisfaction': 4.5}
        assert data['time_range'][0] == '2026-02-18T10:00:00'
        assert data['time_range'][1] == '2026-02-18T11:00:00'


class TestMetricType:
    """Тесты для Enum MetricType"""

    def test_metric_type_values(self):
        """Тест значений Enum"""
        assert MetricType.GAUGE.value == 'gauge'
        assert MetricType.COUNTER.value == 'counter'
        assert MetricType.HISTOGRAM.value == 'histogram'

    def test_metric_type_from_string(self):
        """Тест создания из строки"""
        assert MetricType('gauge') == MetricType.GAUGE
        assert MetricType('counter') == MetricType.COUNTER
        assert MetricType('histogram') == MetricType.HISTOGRAM
