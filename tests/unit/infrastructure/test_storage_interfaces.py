"""
Юнит-тесты для интерфейсов хранилищ метрик и логов.

ТЕСТЫ:
- test_imetrics_storage_interface: проверка интерфейса IMetricsStorage
- test_ilog_storage_interface: проверка интерфейса ILogStorage
"""
import pytest
import inspect
from datetime import datetime
from core.infrastructure.interfaces.metrics_log_interfaces import (
    IMetricsStorage,
    ILogStorage,
)


class TestIMetricsStorageInterface:
    """Тесты для интерфейса IMetricsStorage"""

    def test_imetrics_storage_is_abstract(self):
        """Тест что IMetricsStorage является абстрактным классом"""
        # Попытка создать экземпляр должна вызвать ошибку
        with pytest.raises(TypeError):
            IMetricsStorage()

    def test_imetrics_storage_has_record_method(self):
        """Тест наличия метода record"""
        assert hasattr(IMetricsStorage, 'record')
        assert callable(getattr(IMetricsStorage, 'record'))

    def test_imetrics_storage_has_get_records_method(self):
        """Тест наличия метода get_records"""
        assert hasattr(IMetricsStorage, 'get_records')
        assert callable(getattr(IMetricsStorage, 'get_records'))

    def test_imetrics_storage_has_aggregate_method(self):
        """Тест наличия метода aggregate"""
        assert hasattr(IMetricsStorage, 'aggregate')
        assert callable(getattr(IMetricsStorage, 'aggregate'))

    def test_imetrics_storage_has_clear_old_method(self):
        """Тест наличия метода clear_old"""
        assert hasattr(IMetricsStorage, 'clear_old')
        assert callable(getattr(IMetricsStorage, 'clear_old'))

    def test_imetrics_storage_methods_are_abstract(self):
        """Тест что методы являются абстрактными"""
        from abc import ABC
        
        # Проверяем сигнатуры методов
        record_sig = inspect.signature(IMetricsStorage.record)
        get_records_sig = inspect.signature(IMetricsStorage.get_records)
        aggregate_sig = inspect.signature(IMetricsStorage.aggregate)
        clear_old_sig = inspect.signature(IMetricsStorage.clear_old)

        # Проверка параметров record
        record_params = list(record_sig.parameters.keys())
        assert 'self' in record_params
        assert 'metric' in record_params

        # Проверка параметров get_records
        get_records_params = list(get_records_sig.parameters.keys())
        assert 'self' in get_records_params
        assert 'capability' in get_records_params
        assert 'version' in get_records_params
        assert 'time_range' in get_records_params

        # Проверка параметров aggregate
        aggregate_params = list(aggregate_sig.parameters.keys())
        assert 'self' in aggregate_params
        assert 'capability' in aggregate_params
        assert 'version' in aggregate_params
        assert 'time_range' in aggregate_params

        # Проверка параметров clear_old
        clear_old_params = list(clear_old_sig.parameters.keys())
        assert 'self' in clear_old_params
        assert 'older_than' in clear_old_params

    def test_imetrics_storage_concrete_implementation(self):
        """Тест конкретной реализации интерфейса"""
        from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
        
        class ConcreteMetricsStorage(IMetricsStorage):
            def __init__(self):
                self._records = []

            async def record(self, metric: MetricRecord) -> None:
                self._records.append(metric)

            async def get_records(
                self,
                capability: str,
                version: str = None,
                time_range: tuple = None,
                limit: int = None
            ) -> list:
                result = self._records
                if capability:
                    result = [r for r in result if r.capability == capability]
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
                records = await self.get_records(capability, version, time_range)
                return AggregatedMetrics.from_records(capability, version, records)

            async def clear_old(self, older_than: datetime) -> int:
                initial_count = len(self._records)
                self._records = [r for r in self._records if r.timestamp >= older_than]
                return initial_count - len(self._records)

        # Создание экземпляра должно работать
        storage = ConcreteMetricsStorage()
        assert storage is not None

    def test_imetrics_storage_implementation_works(self):
        """Тест работы конкретной реализации"""
        import asyncio
        from core.models.data.metrics import MetricRecord, MetricType
        
        class ConcreteMetricsStorage(IMetricsStorage):
            def __init__(self):
                self._records = []

            async def record(self, metric: MetricRecord) -> None:
                self._records.append(metric)

            async def get_records(
                self,
                capability: str,
                version: str = None,
                time_range: tuple = None,
                limit: int = None
            ) -> list:
                result = [r for r in self._records if r.capability == capability]
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
            ) -> 'AggregatedMetrics':
                from core.models.data.metrics import AggregatedMetrics
                records = await self.get_records(capability, version, time_range)
                return AggregatedMetrics.from_records(capability, version, records)

            async def clear_old(self, older_than: datetime) -> int:
                initial_count = len(self._records)
                self._records = [r for r in self._records if r.timestamp >= older_than]
                return initial_count - len(self._records)

        async def test():
            storage = ConcreteMetricsStorage()
            
            # Запись метрик
            metric1 = MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            )
            metric2 = MetricRecord(
                agent_id='agent_1',
                capability='test_cap',
                metric_type=MetricType.GAUGE,
                name='success',
                value=1.0,
                version='v1.0'
            )
            
            await storage.record(metric1)
            await storage.record(metric2)
            
            # Получение записей
            records = await storage.get_records('test_cap', 'v1.0')
            assert len(records) == 2
            
            # Агрегация
            aggregated = await storage.aggregate('test_cap', 'v1.0')
            assert aggregated.total_runs == 2
            assert aggregated.success_count == 2
            
            # Очистка
            future_date = datetime.now().replace(year=2100)
            cleared = await storage.clear_old(future_date)
            assert cleared == 2
            
            return True

        result = asyncio.run(test())
        assert result is True


class TestILogStorageInterface:
    """Тесты для интерфейса ILogStorage"""

    def test_ilog_storage_is_abstract(self):
        """Тест что ILogStorage является абстрактным классом"""
        with pytest.raises(TypeError):
            ILogStorage()

    def test_ilog_storage_has_save_method(self):
        """Тест наличия метода save"""
        assert hasattr(ILogStorage, 'save')
        assert callable(getattr(ILogStorage, 'save'))

    def test_ilog_storage_has_get_by_session_method(self):
        """Тест наличия метода get_by_session"""
        assert hasattr(ILogStorage, 'get_by_session')
        assert callable(getattr(ILogStorage, 'get_by_session'))

    def test_ilog_storage_has_get_by_capability_method(self):
        """Тест наличия метода get_by_capability"""
        assert hasattr(ILogStorage, 'get_by_capability')
        assert callable(getattr(ILogStorage, 'get_by_capability'))

    def test_ilog_storage_has_clear_old_method(self):
        """Тест наличия метода clear_old"""
        assert hasattr(ILogStorage, 'clear_old')
        assert callable(getattr(ILogStorage, 'clear_old'))

    def test_ilog_storage_methods_are_abstract(self):
        """Тест что методы являются абстрактными"""
        # Проверяем сигнатуры методов
        save_sig = inspect.signature(ILogStorage.save)
        get_by_session_sig = inspect.signature(ILogStorage.get_by_session)
        get_by_capability_sig = inspect.signature(ILogStorage.get_by_capability)
        clear_old_sig = inspect.signature(ILogStorage.clear_old)

        # Проверка параметров save
        save_params = list(save_sig.parameters.keys())
        assert 'self' in save_params
        assert 'entry' in save_params

        # Проверка параметров get_by_session
        get_by_session_params = list(get_by_session_sig.parameters.keys())
        assert 'self' in get_by_session_params
        assert 'agent_id' in get_by_session_params
        assert 'session_id' in get_by_session_params
        assert 'limit' in get_by_session_params

        # Проверка параметров get_by_capability
        get_by_capability_params = list(get_by_capability_sig.parameters.keys())
        assert 'self' in get_by_capability_params
        assert 'capability' in get_by_capability_params
        assert 'log_type' in get_by_capability_params

        # Проверка параметров clear_old
        clear_old_params = list(clear_old_sig.parameters.keys())
        assert 'self' in clear_old_params
        assert 'older_than' in clear_old_params

    def test_ilog_storage_concrete_implementation(self):
        """Тест конкретной реализации интерфейса"""
        from core.models.data.benchmark import LogEntry, LogType
        
        class ConcreteLogStorage(ILogStorage):
            def __init__(self):
                self._entries = []

            async def save(self, entry: LogEntry) -> None:
                self._entries.append(entry)

            async def get_by_session(
                self,
                agent_id: str,
                session_id: str,
                limit: int = None
            ) -> list:
                result = [
                    e for e in self._entries
                    if e.agent_id == agent_id and e.session_id == session_id
                ]
                if limit:
                    result = result[:limit]
                return result

            async def get_by_capability(
                self,
                capability: str,
                log_type: str = None,
                limit: int = None
            ) -> list:
                result = [e for e in self._entries if e.capability == capability]
                if log_type:
                    result = [e for e in result if e.log_type.value == log_type]
                if limit:
                    result = result[:limit]
                return result

            async def clear_old(self, older_than: datetime) -> int:
                initial_count = len(self._entries)
                self._entries = [e for e in self._entries if e.timestamp >= older_than]
                return initial_count - len(self._entries)

        # Создание экземпляра должно работать
        storage = ConcreteLogStorage()
        assert storage is not None

    def test_ilog_storage_implementation_works(self):
        """Тест работы конкретной реализации"""
        import asyncio
        from core.models.data.benchmark import LogEntry, LogType
        
        class ConcreteLogStorage(ILogStorage):
            def __init__(self):
                self._entries = []

            async def save(self, entry: LogEntry) -> None:
                self._entries.append(entry)

            async def get_by_session(
                self,
                agent_id: str,
                session_id: str,
                limit: int = None
            ) -> list:
                result = [
                    e for e in self._entries
                    if e.agent_id == agent_id and e.session_id == session_id
                ]
                if limit:
                    result = result[:limit]
                return result

            async def get_by_capability(
                self,
                capability: str,
                log_type: str = None,
                limit: int = None
            ) -> list:
                result = [e for e in self._entries if e.capability == capability]
                if log_type:
                    result = [e for e in result if e.log_type.value == log_type]
                if limit:
                    result = result[:limit]
                return result

            async def clear_old(self, older_than: datetime) -> int:
                initial_count = len(self._entries)
                self._entries = [e for e in self._entries if e.timestamp >= older_than]
                return initial_count - len(self._entries)

        async def test():
            storage = ConcreteLogStorage()
            
            # Сохранение логов
            entry1 = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'capability': 'test_cap'},
                capability='test_cap'
            )
            entry2 = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.ERROR,
                data={'error': 'test error'},
                capability='test_cap'
            )
            
            await storage.save(entry1)
            await storage.save(entry2)
            
            # Получение по сессии
            session_logs = await storage.get_by_session('agent_1', 'session_123')
            assert len(session_logs) == 2
            
            # Получение по способности
            cap_logs = await storage.get_by_capability('test_cap')
            assert len(cap_logs) == 2
            
            # Получение по типу лога
            error_logs = await storage.get_by_capability('test_cap', log_type='error')
            assert len(error_logs) == 1
            
            # Очистка
            future_date = datetime.now().replace(year=2100)
            cleared = await storage.clear_old(future_date)
            assert cleared == 2
            
            return True

        result = asyncio.run(test())
        assert result is True
