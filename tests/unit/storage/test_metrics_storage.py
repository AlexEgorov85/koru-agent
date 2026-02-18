"""
Юнит-тесты для FileSystemMetricsStorage.

ТЕСТЫ:
- test_record_metric: запись метрики
- test_get_records_filtering: фильтрация записей
- test_aggregate_metrics: агрегация метрик
- test_clear_old_metrics: очистка старых метрик
- test_get_capabilities: получение списка capability
- test_get_versions: получение списка версий
"""
import pytest
import asyncio
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
from core.infrastructure.metrics_storage import FileSystemMetricsStorage


@pytest.fixture
def temp_storage():
    """Фикстура для временного хранилища"""
    temp_dir = tempfile.mkdtemp()
    storage = FileSystemMetricsStorage(base_dir=Path(temp_dir))
    yield storage
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_metric():
    """Фикстура для тестовой метрики"""
    return MetricRecord(
        agent_id='agent_1',
        capability='test_capability',
        metric_type=MetricType.GAUGE,
        name='success',
        value=1.0,
        version='v1.0',
        session_id='session_123'
    )


class TestFileSystemMetricsStorage:
    """Тесты для FileSystemMetricsStorage"""

    @pytest.mark.asyncio
    async def test_record_metric(self, temp_storage, sample_metric):
        """Тест записи метрики"""
        # Запись метрики
        await temp_storage.record(sample_metric)

        # Проверка файла метрик
        metrics_file = temp_storage._get_metrics_file(
            sample_metric.capability,
            sample_metric.version,
            sample_metric.timestamp
        )

        assert metrics_file.exists()

        # Проверка содержимого
        data = temp_storage._load_metrics_file(metrics_file)
        assert len(data) == 1
        assert data[0]['capability'] == 'test_capability'
        assert data[0]['version'] == 'v1.0'
        assert data[0]['value'] == 1.0

    @pytest.mark.asyncio
    async def test_record_multiple_metrics(self, temp_storage):
        """Тест записи нескольких метрик"""
        metrics = [
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
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        # Проверка количества записей
        records = await temp_storage.get_records('test_cap', 'v1.0')
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_get_records_filtering(self, temp_storage):
        """Тест фильтрации записей"""
        base_time = datetime.now()

        # Запись метрик с разными версиями
        metrics = [
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0',
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v2.0',
                timestamp=base_time
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0',
                timestamp=base_time - timedelta(hours=1)
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        # Получение всех записей
        all_records = await temp_storage.get_records('test_cap')
        assert len(all_records) == 3

        # Получение записей конкретной версии
        v1_records = await temp_storage.get_records('test_cap', 'v1.0')
        assert len(v1_records) == 2

        v2_records = await temp_storage.get_records('test_cap', 'v2.0')
        assert len(v2_records) == 1

    @pytest.mark.asyncio
    async def test_get_records_time_range(self, temp_storage):
        """Тест фильтрации по времени"""
        base_time = datetime.now()

        metrics = [
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0',
                timestamp=base_time - timedelta(days=2)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0',
                timestamp=base_time - timedelta(days=1)
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0',
                timestamp=base_time
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        # Получение записей за последний день
        time_range = (base_time - timedelta(hours=23), base_time + timedelta(seconds=1))
        records = await temp_storage.get_records('test_cap', 'v1.0', time_range)
        assert len(records) == 1

        # Получение записей за последние 3 дня
        time_range = (base_time - timedelta(days=3), base_time + timedelta(seconds=1))
        records = await temp_storage.get_records('test_cap', 'v1.0', time_range)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_get_records_limit(self, temp_storage):
        """Тест ограничения количества записей"""
        for i in range(10):
            metric = MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            )
            await temp_storage.record(metric)

        # Получение с ограничением
        records = await temp_storage.get_records('test_cap', 'v1.0', limit=5)
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, temp_storage):
        """Тест агрегации метрик"""
        # Запись метрик для агрегации
        metrics = [
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
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=100.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=150.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='execution_time_ms',
                value=200.0,
                version='v1.0'
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        # Агрегация
        aggregated = await temp_storage.aggregate('test_cap', 'v1.0')

        assert aggregated.capability == 'test_cap'
        assert aggregated.version == 'v1.0'
        assert aggregated.total_runs == 3
        assert aggregated.success_count == 2
        assert aggregated.failure_count == 1
        assert aggregated.accuracy == pytest.approx(2/3, rel=1e-5)
        assert aggregated.avg_execution_time_ms == pytest.approx(150.0)

    @pytest.mark.asyncio
    async def test_aggregate_empty_records(self, temp_storage):
        """Тест агрегации пустых записей"""
        aggregated = await temp_storage.aggregate('nonexistent_cap', 'v1.0')

        assert aggregated.capability == 'nonexistent_cap'
        assert aggregated.version == 'v1.0'
        assert aggregated.total_runs == 0
        assert aggregated.accuracy == 0.0

    @pytest.mark.asyncio
    async def test_clear_old_metrics(self, temp_storage):
        """Тест очистки старых метрик"""
        old_date = datetime.now() - timedelta(days=10)
        new_date = datetime.now()

        # Запись старых метрик
        old_metric = MetricRecord(
            agent_id='agent_1',
            capability='test_cap',
            metric_type=MetricType.GAUGE,
            name='success',
            value=1.0,
            version='v1.0',
            timestamp=old_date
        )
        await temp_storage.record(old_metric)

        # Запись новых метрик
        new_metric = MetricRecord(
            agent_id='agent_1',
            capability='test_cap',
            metric_type=MetricType.GAUGE,
            name='success',
            value=1.0,
            version='v1.0',
            timestamp=new_date
        )
        await temp_storage.record(new_metric)

        # Очистка старых (старше 5 дней)
        threshold = datetime.now() - timedelta(days=5)
        deleted = await temp_storage.clear_old(threshold)

        assert deleted == 1

        # Проверка что остались только новые
        records = await temp_storage.get_records('test_cap', 'v1.0')
        assert len(records) == 1
        assert records[0].timestamp.date() == new_date.date()

    @pytest.mark.asyncio
    async def test_get_capabilities(self, temp_storage):
        """Тест получения списка capability"""
        # Запись метрик для разных capability
        metrics = [
            MetricRecord(
                agent_id='agent_1',
                capability='capability_one',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='capability_two',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='capability_three',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        capabilities = await temp_storage.get_capabilities()

        assert len(capabilities) == 3
        assert 'capability/one' in capabilities or 'capability_one' in capabilities
        assert 'capability/two' in capabilities or 'capability_two' in capabilities
        assert 'capability/three' in capabilities or 'capability_three' in capabilities

    @pytest.mark.asyncio
    async def test_get_versions(self, temp_storage):
        """Тест получения списка версий"""
        # Запись метрик для разных версий
        metrics = [
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
                version='v2.0'
            ),
            MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v3.0'
            ),
        ]

        for metric in metrics:
            await temp_storage.record(metric)

        versions = await temp_storage.get_versions('test_cap')

        assert len(versions) == 3
        assert 'v1.0' in versions or 'v1/0' in versions
        assert 'v2.0' in versions or 'v2/0' in versions
        assert 'v3.0' in versions or 'v3/0' in versions

    @pytest.mark.asyncio
    async def test_get_aggregated(self, temp_storage):
        """Тест получения сохранённых агрегированных метрик"""
        # Запись метрик
        metrics = [
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

        for metric in metrics:
            await temp_storage.record(metric)

        # Получение агрегированных метрик
        aggregated = await temp_storage.get_aggregated('test_cap', 'v1.0')

        assert aggregated is not None
        assert aggregated.capability == 'test_cap'
        assert aggregated.version == 'v1.0'
        assert aggregated.accuracy == 0.5

    @pytest.mark.asyncio
    async def test_get_aggregated_nonexistent(self, temp_storage):
        """Тест получения несуществующих агрегированных метрик"""
        aggregated = await temp_storage.get_aggregated('nonexistent', 'v1.0')

        assert aggregated is None

    @pytest.mark.asyncio
    async def test_latest_metrics_updated(self, temp_storage):
        """Тест обновления latest метрик"""
        # Запись нескольких метрик
        for i in range(5):
            metric = MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            )
            await temp_storage.record(metric)

        # Проверка latest файла
        latest_file = temp_storage._get_latest_file('test_cap')
        assert latest_file.exists()

        data = temp_storage._load_metrics_file(latest_file)
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_concurrent_record(self, temp_storage):
        """Тест конкурентной записи"""
        async def record_metric(value: float):
            metric = MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=value,
                version='v1.0'
            )
            await temp_storage.record(metric)

        # Параллельная запись
        await asyncio.gather(*[record_metric(i) for i in range(10)])

        # Проверка что все записи сохранились
        records = await temp_storage.get_records('test_cap', 'v1.0')
        assert len(records) == 10

    @pytest.mark.asyncio
    async def test_default_version(self, temp_storage):
        """Тест версии по умолчанию"""
        metric = MetricRecord(
            agent_id='agent_1',
            capability='test_cap',
            metric_type=MetricType.GAUGE,
            name='success',
            value=1.0,
            version=None  # None версия
        )
        await temp_storage.record(metric)

        # Проверка что использовалась версия 'default'
        records = await temp_storage.get_records('test_cap', 'default')
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_directory_structure_created(self, temp_storage):
        """Тест создания структуры директорий"""
        metric = MetricRecord(
            agent_id='agent_1',
            capability='test/capability',
            metric_type=MetricType.GAUGE,
            name='success',
            value=1.0,
            version='v1.0'
        )
        await temp_storage.record(metric)

        # Проверка что директории созданы
        capability_dir = temp_storage._get_capability_dir('test/capability')
        version_dir = temp_storage._get_version_dir('test/capability', 'v1.0')

        assert capability_dir.exists()
        assert version_dir.exists()

    @pytest.mark.asyncio
    async def test_metrics_file_json_format(self, temp_storage, sample_metric):
        """Тест JSON формата файла метрик"""
        await temp_storage.record(sample_metric)

        metrics_file = temp_storage._get_metrics_file(
            sample_metric.capability,
            sample_metric.version,
            sample_metric.timestamp
        )

        # Проверка что файл валидный JSON
        with open(metrics_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert 'agent_id' in data[0]
        assert 'capability' in data[0]
        assert 'metric_type' in data[0]
