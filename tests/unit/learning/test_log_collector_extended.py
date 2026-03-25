"""
Тесты для LogCollector с расширенными функциями.

TESTS:
- test_quality_score_calculation: тесты расчёта оценки качества
- test_execution_context_logging: тесты логирования контекста
- test_benchmark_scenario_linking: тесты связи с бенчмарками
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from core.infrastructure.event_bus import EventBus, Event, EventType
from core.benchmarks.benchmark_models import LogEntry, LogType
from core.infrastructure.log_collector import LogCollector


class MockLogStorage:
    """Моковое хранилище логов для тестов"""

    def __init__(self):
        self.entries = []

    async def save(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    async def get_by_session(self, agent_id: str, session_id: str, limit: int = None) -> list:
        return self.entries

    async def get_by_capability(self, capability: str, log_type: str = None, limit: int = None) -> list:
        entries = self.entries
        if log_type:
            entries = [e for e in entries if e.log_type.value == log_type]
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


class TestQualityScoreCalculation:
    """Тесты расчёта оценки качества шага"""

    @pytest.mark.asyncio
    async def test_quality_score_success_base(self, collector):
        """Тест базовой оценки за успешность"""
        data = {'success': True}
        score = await collector._calculate_quality_score(data)
        
        assert score >= 0.5  # Базовая + успешность
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_quality_score_failure(self, collector):
        """Тест оценки для неудачного шага"""
        data = {'success': False}
        score = await collector._calculate_quality_score(data)
        
        assert score == 0.2  # Неудачный шаг

    @pytest.mark.asyncio
    async def test_quality_score_fast_execution(self, collector):
        """Тест оценки за быстрое выполнение"""
        data = {'success': True, 'execution_time_ms': 50}
        score = await collector._calculate_quality_score(data)
        
        assert score >= 0.8  # Базовая + успешность + быстрое выполнение

    @pytest.mark.asyncio
    async def test_quality_score_slow_execution(self, collector):
        """Тест оценки за медленное выполнение"""
        data = {'success': True, 'execution_time_ms': 1000}
        score = await collector._calculate_quality_score(data)
        
        # Только базовая + успешность, без бонуса за время
        assert score <= 0.9  # 0.5 + 0.3 + возможные бонусы за токены

    @pytest.mark.asyncio
    async def test_quality_score_low_tokens(self, collector):
        """Тест оценки за малое использование токенов"""
        data = {'success': True, 'tokens_used': 50}
        score = await collector._calculate_quality_score(data)
        
        assert score >= 0.8  # Базовая + успешность + мало токенов

    @pytest.mark.asyncio
    async def test_quality_score_with_progress(self, collector):
        """Тест оценки с прогрессом к цели"""
        data = {'success': True, 'goal_progress': 1.0}
        score = await collector._calculate_quality_score(data)
        
        assert score == 1.0  # Максимальная оценка

    @pytest.mark.asyncio
    async def test_quality_score_bounds(self, collector):
        """Тест границ оценки"""
        # Минимальная оценка
        score_min = await collector._calculate_quality_score({'success': False})
        assert 0.0 <= score_min <= 1.0
        
        # Максимальная оценка
        score_max = await collector._calculate_quality_score({
            'success': True,
            'execution_time_ms': 50,
            'tokens_used': 50,
            'goal_progress': 1.0
        })
        assert 0.0 <= score_max <= 1.0


class TestExecutionContextLogging:
    """Тесты логирования контекста выполнения"""

    @pytest.mark.asyncio
    async def test_capability_selected_with_context(self, collector, storage):
        """Тест логирования выбора способности с контекстом"""
        await collector.initialize()
        
        event = Event(
            event_type=EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'test_agent',
                'session_id': 'test_session',
                'capability': 'planning.create_plan',
                'reasoning': 'Test reasoning',
                'pattern_id': 'react',
                'execution_context': {
                    'step_number': 1,
                    'available_capabilities': ['cap1', 'cap2']
                }
            },
            timestamp=datetime.now()
        )
        
        await collector._on_capability_selected(event)
        
        assert len(storage.entries) == 1
        entry = storage.entries[0]
        
        assert entry.execution_context is not None
        assert entry.execution_context['step_number'] == 1
        assert entry.step_quality_score is not None
        assert 0.0 <= entry.step_quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_capability_selected_quality_score_saved(self, collector, storage):
        """Тест сохранения оценки качества"""
        await collector.initialize()
        
        event = Event(
            event_type=EventType.CAPABILITY_SELECTED,
            data={
                'agent_id': 'test_agent',
                'session_id': 'test_session',
                'capability': 'planning.create_plan',
                'success': True,
                'execution_time_ms': 50,
                'tokens_used': 100
            },
            timestamp=datetime.now()
        )
        
        await collector._on_capability_selected(event)
        
        entry = storage.entries[0]
        assert entry.step_quality_score > 0.8  # Высокая оценка за хорошие метрики


class TestBenchmarkScenarioLinking:
    """Тесты связи логов с бенчмарками"""

    @pytest.mark.asyncio
    async def test_benchmark_event_with_scenario_id(self, collector, storage):
        """Тест логирования события бенчмарка с scenario_id"""
        await collector.initialize()
        
        event = Event(
            event_type=EventType.BENCHMARK_COMPLETED,
            data={
                'scenario_id': 'benchmark_scenario_001',
                'capability': 'planning.create_plan',
                'version': 'v1.0',
                'success': True,
                'overall_score': 0.95,
                'metrics': {'accuracy': 0.9}
            },
            timestamp=datetime.now()
        )
        
        await collector._on_benchmark_event(event)
        
        assert len(storage.entries) == 1
        entry = storage.entries[0]
        
        assert entry.benchmark_scenario_id == 'benchmark_scenario_001'
        assert entry.data['benchmark_scenario_id'] == 'benchmark_scenario_001'
        assert entry.log_type == LogType.BENCHMARK

    @pytest.mark.asyncio
    async def test_benchmark_failed_with_scenario_id(self, collector, storage):
        """Тест логирования неудачи бенчмарка с scenario_id"""
        await collector.initialize()
        
        event = Event(
            event_type=EventType.BENCHMARK_FAILED,
            data={
                'scenario_id': 'benchmark_scenario_002',
                'version': 'v1.0',
                'error': 'Test error'
            },
            timestamp=datetime.now()
        )
        
        await collector._on_benchmark_event(event)
        
        entry = storage.entries[0]
        assert entry.benchmark_scenario_id == 'benchmark_scenario_002'
        assert entry.data['benchmark_scenario_id'] == 'benchmark_scenario_002'
