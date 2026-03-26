"""
Юнит-тесты для LogCollector.

ТЕСТЫ:
- test_log_collector_initialization: инициализация и подписки
- test_on_capability_selected_logs: логирование выбора способности
- test_on_error_logs: логирование ошибок
- test_on_benchmark_logs: логирование бенчмарков
- test_get_session_logs: получение логов сессии
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from core.infrastructure.event_bus import EventBus, Event, EventType
from core.services.benchmarks.benchmark_models import LogEntry, LogType
from core.infrastructure.log_collector import LogCollector


class MockLogStorage:
    """Моковое хранилище логов для тестов"""

    def __init__(self):
        self.entries = []
        self.by_session = {}
        self.by_capability = {}

    async def save(self, entry: LogEntry) -> None:
        self.entries.append(entry)

        # Индексация по сессии
        key = (entry.agent_id, entry.session_id)
        if key not in self.by_session:
            self.by_session[key] = []
        self.by_session[key].append(entry)

        # Индексация по capability
        if entry.capability:
            if entry.capability not in self.by_capability:
                self.by_capability[entry.capability] = []
            self.by_capability[entry.capability].append(entry)

    async def get_by_session(
        self,
        agent_id: str,
        session_id: str,
        limit: int = None
    ) -> list:
        key = (agent_id, session_id)
        entries = self.by_session.get(key, [])
        if limit:
            entries = entries[-limit:]
        return entries

    async def get_by_capability(
        self,
        capability: str,
        log_type: str = None,
        limit: int = None
    ) -> list:
        entries = self.by_capability.get(capability, [])
        if log_type:
            entries = [e for e in entries if e.log_type.value == log_type]
        if limit:
            entries = entries[:limit]
        return entries

    async def clear_old(self, older_than: datetime) -> int:
        return 0


@pytest.fixture
def event_bus():
    """Фикстура EventBus"""
    return EventBus()


@pytest.fixture
def storage():
    """Фикстура хранилища"""
    return MockLogStorage()


@pytest.fixture
def collector(event_bus, storage):
    """Фикстура LogCollector"""
    return LogCollector(event_bus, storage)


class TestLogCollectorInitialization:
    """Тесты инициализации LogCollector"""

    @pytest.mark.asyncio
    async def test_log_collector_initialization(self, collector):
        """Тест инициализации сборщика логов"""
        assert collector.is_initialized is False
        assert collector.subscriptions_count == 0

        # Инициализация
        await collector.initialize()

        assert collector.is_initialized is True
        assert collector.subscriptions_count == 11  # 11 типов событий

    @pytest.mark.asyncio
    async def test_double_initialization(self, collector):
        """Тест повторной инициализации"""
        await collector.initialize()
        initial_count = collector.subscriptions_count

        # Повторная инициализация
        await collector.initialize()

        assert collector.subscriptions_count == initial_count

    @pytest.mark.asyncio
    async def test_shutdown(self, collector):
        """Тест завершения работы"""
        await collector.initialize()
        assert collector.is_initialized is True

        await collector.shutdown()

        assert collector.is_initialized is False


class TestCapabilitySelectedHandler:
    """Тесты обработчика CAPABILITY_SELECTED"""

    @pytest.mark.asyncio
    async def test_on_capability_selected_logs(self, collector, storage, event_bus):
        """Тест логирования выбора способности"""
        await collector.initialize()

        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'planning.create_plan',
                'reasoning': 'Это лучший способ создать план',
                'pattern_id': 'pattern_456',
                'parameters': {'param1': 'value1'},
                'confidence': 0.95,
                'version': 'v1.0'
            },
            correlation_id='corr_789'
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка записанного лога
        assert len(storage.entries) == 1
        entry = storage.entries[0]

        assert entry.agent_id == 'agent_1'
        assert entry.session_id == 'session_123'
        assert entry.log_type == LogType.CAPABILITY_SELECTION
        assert entry.capability == 'planning.create_plan'
        assert entry.version == 'v1.0'
        assert entry.correlation_id == 'corr_789'

        # Проверка данных
        assert entry.data['capability'] == 'planning.create_plan'
        assert entry.data['reasoning'] == 'Это лучший способ создать план'
        assert entry.data['pattern_id'] == 'pattern_456'
        assert entry.data['parameters'] == {'param1': 'value1'}
        assert entry.data['confidence'] == 0.95

    @pytest.mark.asyncio
    async def test_on_capability_selected_without_reasoning(self, collector, storage, event_bus):
        """Тест логирования без reasoning"""
        await collector.initialize()

        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'test_cap'
                # reasoning отсутствует
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.data['reasoning'] == ''

    @pytest.mark.asyncio
    async def test_on_capability_selected_without_capability(self, collector, storage, event_bus):
        """Тест пропуска события без capability"""
        await collector.initialize()

        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123'
                # capability отсутствует
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Лог не должен быть записан
        assert len(storage.entries) == 0


class TestErrorHandler:
    """Тесты обработчика ERROR_OCCURRED"""

    @pytest.mark.asyncio
    async def test_on_error_occurred_logs(self, collector, storage, event_bus):
        """Тест логирования ошибки"""
        await collector.initialize()

        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'test_capability',
                'error_type': 'ValidationError',
                'error_message': 'Неверный формат данных',
                'action': 'validate_input',
                'stack_trace': 'File "test.py", line 10...',
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        assert len(storage.entries) == 1
        entry = storage.entries[0]

        assert entry.log_type == LogType.ERROR
        assert entry.capability == 'test_capability'

        # Проверка данных ошибки
        assert entry.data['error_type'] == 'ValidationError'
        assert entry.data['error_message'] == 'Неверный формат данных'
        assert entry.data['capability'] == 'test_capability'
        assert entry.data['action'] == 'validate_input'

    @pytest.mark.asyncio
    async def test_on_error_sanitizes_large_data(self, collector, storage, event_bus):
        """Тест санитаризации больших данных"""
        await collector.initialize()

        large_data = 'x' * 2000  # 2000 символов

        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'test_cap',
                'error_type': 'TestError',
                'input_data': large_data
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        # Данные должны быть обрезаны
        assert '... (truncated)' in entry.data['input_data']
        assert len(entry.data['input_data']) <= 1015  # 1000 + '... (truncated)'

    @pytest.mark.asyncio
    async def test_on_error_without_capability(self, collector, storage, event_bus):
        """Тест ошибки без capability"""
        await collector.initialize()

        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'error_type': 'TestError'
                # capability отсутствует
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.capability == 'unknown'


class TestBenchmarkHandler:
    """Тесты обработчика событий бенчмарка"""

    @pytest.mark.asyncio
    async def test_on_benchmark_started(self, collector, storage, event_bus):
        """Тест логирования начала бенчмарка"""
        await collector.initialize()

        await event_bus.publish(
            EventType.BENCHMARK_STARTED,
            data={
                'agent_id': 'benchmark_system',
                'scenario_id': 'scenario_001',
                'capability': 'test_capability',
                'version': 'v1.0'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        assert len(storage.entries) == 1
        entry = storage.entries[0]

        assert entry.log_type == LogType.BENCHMARK
        assert entry.data['event_type'] == 'benchmark.started'
        assert entry.data['scenario_id'] == 'scenario_001'

    @pytest.mark.asyncio
    async def test_on_benchmark_completed(self, collector, storage, event_bus):
        """Тест логирования завершения бенчмарка"""
        await collector.initialize()

        await event_bus.publish(
            EventType.BENCHMARK_COMPLETED,
            data={
                'scenario_id': 'scenario_001',
                'capability': 'test_capability',
                'success': True,
                'overall_score': 0.85,
                'metrics': {'accuracy': 0.85, 'speed': 100.0}
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.data['success'] is True
        assert entry.data['overall_score'] == 0.85
        assert entry.data['metrics'] == {'accuracy': 0.85, 'speed': 100.0}


class TestOptimizationHandler:
    """Тесты обработчика событий оптимизации"""

    @pytest.mark.asyncio
    async def test_on_optimization_cycle_started(self, collector, storage, event_bus):
        """Тест логирования начала оптимизации"""
        await collector.initialize()

        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_STARTED,
            data={
                'capability': 'test_capability',
                'mode': 'accuracy',
                'target_accuracy': 0.95
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        assert len(storage.entries) == 1
        entry = storage.entries[0]

        assert entry.log_type == LogType.OPTIMIZATION
        assert entry.data['event_type'] == 'optimization.cycle.started'
        assert entry.data['mode'] == 'accuracy'

    @pytest.mark.asyncio
    async def test_on_optimization_cycle_completed(self, collector, storage, event_bus):
        """Тест логирования завершения оптимизации"""
        await collector.initialize()

        await event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            data={
                'capability': 'test_capability',
                'from_version': 'v1.0',
                'to_version': 'v2.0',
                'iterations': 5,
                'improvements': {'accuracy': 12.5},
                'target_achieved': True
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.data['from_version'] == 'v1.0'
        assert entry.data['to_version'] == 'v2.0'
        assert entry.data['iterations'] == 5
        assert entry.data['target_achieved'] is True


class TestVersionHandler:
    """Тесты обработчика событий версий"""

    @pytest.mark.asyncio
    async def test_on_version_promoted(self, collector, storage, event_bus):
        """Тест логирования продвижения версии"""
        await collector.initialize()

        await event_bus.publish(
            EventType.VERSION_PROMOTED,
            data={
                'capability': 'test_capability',
                'from_version': 'v1.0',
                'to_version': 'v2.0',
                'reason': 'Улучшение accuracy на 10%'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.data['event_type'] == 'version.promoted'
        assert entry.data['reason'] == 'Улучшение accuracy на 10%'

    @pytest.mark.asyncio
    async def test_on_version_rejected(self, collector, storage, event_bus):
        """Тест логирования отклонения версии"""
        await collector.initialize()

        await event_bus.publish(
            EventType.VERSION_REJECTED,
            data={
                'capability': 'test_capability',
                'from_version': 'v1.0',
                'to_version': 'v2.0',
                'reason': 'Снижение производительности'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        entry = storage.entries[0]
        assert entry.data['event_type'] == 'version.rejected'


class TestGetLogs:
    """Тесты получения логов"""

    @pytest.mark.asyncio
    async def test_get_session_logs(self, collector, storage):
        """Тест получения логов сессии"""
        # Добавление тестовых логов
        storage.entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'step': 1}
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.ERROR,
                data={'step': 2}
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_456',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'step': 3}
            ),
        ]

        # Обновление индексов
        for entry in storage.entries:
            key = (entry.agent_id, entry.session_id)
            if key not in storage.by_session:
                storage.by_session[key] = []
            storage.by_session[key].append(entry)

        # Получение логов сессии
        logs = await collector.get_session_logs('agent_1', 'session_123')

        assert len(logs) == 2
        assert all(l.session_id == 'session_123' for l in logs)

    @pytest.mark.asyncio
    async def test_get_session_logs_with_limit(self, collector, storage):
        """Тест ограничения логов сессии"""
        for i in range(10):
            entry = LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_123',
                log_type=LogType.CAPABILITY_SELECTION,
                data={'index': i}
            )
            storage.entries.append(entry)

            key = ('agent_1', 'session_123')
            if key not in storage.by_session:
                storage.by_session[key] = []
            storage.by_session[key].append(entry)

        logs = await collector.get_session_logs('agent_1', 'session_123', limit=5)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_get_capability_logs(self, collector, storage):
        """Тест получения логов по capability"""
        storage.entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_2',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='other_cap'
            ),
        ]

        for entry in storage.entries:
            if entry.capability:
                if entry.capability not in storage.by_capability:
                    storage.by_capability[entry.capability] = []
                storage.by_capability[entry.capability].append(entry)

        logs = await collector.get_capability_logs('test_cap')

        assert len(logs) == 2
        assert all(l.capability == 'test_cap' for l in logs)

    @pytest.mark.asyncio
    async def test_get_capability_logs_by_type(self, collector, storage):
        """Тест фильтрации логов по типу"""
        storage.entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_2',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={},
                capability='test_cap'
            ),
        ]

        for entry in storage.entries:
            if entry.capability:
                if entry.capability not in storage.by_capability:
                    storage.by_capability[entry.capability] = []
                storage.by_capability[entry.capability].append(entry)

        logs = await collector.get_capability_logs('test_cap', log_type='capability_selection')

        assert len(logs) == 1
        assert logs[0].log_type == LogType.CAPABILITY_SELECTION

    @pytest.mark.asyncio
    async def test_get_error_logs(self, collector, storage):
        """Тест получения логов ошибок"""
        storage.entries = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.CAPABILITY_SELECTION,
                data={},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.ERROR,
                data={'error': 'test'},
                capability='test_cap'
            ),
        ]

        for entry in storage.entries:
            if entry.capability:
                if entry.capability not in storage.by_capability:
                    storage.by_capability[entry.capability] = []
                storage.by_capability[entry.capability].append(entry)

        error_logs = await collector.get_error_logs('test_cap')

        assert len(error_logs) == 1
        assert error_logs[0].log_type == LogType.ERROR


class TestEndToEnd:
    """Сквозные тесты LogCollector"""

    @pytest.mark.asyncio
    async def test_full_logging_flow(self, collector, storage, event_bus):
        """Тест полного потока логирования"""
        await collector.initialize()

        # 1. Выбор способности
        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'planning.create_plan',
                'reasoning': 'Создаю план',
                'version': 'v1.0'
            }
        )

        # 2. Ошибка при выполнении
        await event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_123',
                'capability': 'planning.create_plan',
                'error_type': 'PlanError',
                'error_message': 'Не удалось создать план'
            }
        )

        # 3. Бенчмарк
        await event_bus.publish(
            EventType.BENCHMARK_COMPLETED,
            data={
                'scenario_id': 'scenario_001',
                'capability': 'planning.create_plan',
                'success': False,
                'overall_score': 0.3
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка всех логов
        assert len(storage.entries) == 3

        # Проверка логов сессии
        session_logs = await collector.get_session_logs('agent_1', 'session_123')
        assert len(session_logs) == 2  # выбор способности + ошибка

        # Проверка логов capability (включая бенчмарк)
        cap_logs = await collector.get_capability_logs('planning.create_plan')
        assert len(cap_logs) == 3  # выбор + ошибка + бенчмарк

        # Проверка логов ошибок
        error_logs = await collector.get_error_logs('planning.create_plan')
        assert len(error_logs) == 1

    @pytest.mark.asyncio
    async def test_multiple_agents_isolation(self, collector, storage, event_bus):
        """Тест изоляции логов разных агентов"""
        await collector.initialize()

        # Логи agent_1
        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_1',
                'session_id': 'session_a',
                'capability': 'test_cap',
                'reasoning': 'Agent 1 reasoning'
            }
        )

        # Логи agent_2
        await event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'agent_2',
                'session_id': 'session_b',
                'capability': 'test_cap',
                'reasoning': 'Agent 2 reasoning'
            }
        )

        import asyncio
        await asyncio.sleep(0.01)

        # Проверка изоляции
        agent1_logs = await collector.get_session_logs('agent_1', 'session_a')
        agent2_logs = await collector.get_session_logs('agent_2', 'session_b')

        assert len(agent1_logs) == 1
        assert len(agent2_logs) == 1
        assert agent1_logs[0].data['reasoning'] == 'Agent 1 reasoning'
        assert agent2_logs[0].data['reasoning'] == 'Agent 2 reasoning'
