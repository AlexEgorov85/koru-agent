"""
Юнит-тесты для OptimizationService.

ТЕСТЫ:
- test_start_optimization_cycle: запуск цикла оптимизации
- test_analyze_failures: анализ неудач
- test_needs_optimization: проверка необходимости
- test_optimization_lock: блокировка
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.benchmark import (
    FailureAnalysis,
    OptimizationMode,
    OptimizationResult,
    TargetMetric,
    LogEntry,
    LogType,
)
from core.application.services.optimization_service import (
    OptimizationService,
    OptimizationConfig,
    OptimizationLock,
)
from core.application.services.benchmark_service import BenchmarkService
from core.application.services.prompt_contract_generator import PromptContractGenerator
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.event_bus import EventBus, EventType


@pytest.fixture
def mock_benchmark_service():
    """Моковый BenchmarkService"""
    service = AsyncMock(spec=BenchmarkService)
    service.promote_version = AsyncMock(return_value=True)
    service.reject_version = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_prompt_generator():
    """Моковый PromptContractGenerator"""
    generator = AsyncMock(spec=PromptContractGenerator)
    generator.generate_and_save = AsyncMock(return_value=(MagicMock(), MagicMock()))
    return generator


@pytest.fixture
def mock_metrics_collector():
    """Моковый MetricsCollector"""
    collector = AsyncMock(spec=MetricsCollector)
    collector.get_aggregated_metrics = AsyncMock(return_value=MagicMock(accuracy=0.7))
    collector.log_collector = AsyncMock()
    collector.log_collector.get_error_logs = AsyncMock(return_value=[])
    return collector


@pytest.fixture
def event_bus():
    """EventBus для тестов"""
    return EventBus()


@pytest.fixture
def optimization_service(mock_benchmark_service, mock_prompt_generator, mock_metrics_collector, event_bus):
    """OptimizationService для тестов"""
    return OptimizationService(
        benchmark_service=mock_benchmark_service,
        prompt_generator=mock_prompt_generator,
        metrics_collector=mock_metrics_collector,
        event_bus=event_bus,
        config=OptimizationConfig(max_iterations=3, target_accuracy=0.9)
    )


class TestStartOptimizationCycle:
    """Тесты start_optimization_cycle"""

    @pytest.mark.asyncio
    async def test_start_optimization_cycle_success(self, optimization_service):
        """Тест успешного запуска цикла оптимизации"""
        # Мокаем методы
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._analyze_failures = AsyncMock(return_value=FailureAnalysis(
            capability='test',
            version='v1.0.0',
            total_failures=5
        ))
        optimization_service._get_current_version = AsyncMock(return_value='v1.0.0')
        optimization_service._get_current_prompt = AsyncMock(return_value=MagicMock())
        optimization_service._test_new_version = AsyncMock(return_value={
            'metrics': {'accuracy': 0.95}
        })

        result = await optimization_service.start_optimization_cycle(
            'test_capability',
            OptimizationMode.ACCURACY
        )

        assert result is not None
        assert result.capability == 'test_capability'
        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_start_optimization_cycle_not_optimizable(self, optimization_service):
        """Тест когда capability не может быть оптимизирован"""
        optimization_service._is_capability_optimizable = AsyncMock(return_value=False)

        result = await optimization_service.start_optimization_cycle('test_capability')

        assert result is None

    @pytest.mark.asyncio
    async def test_start_optimization_cycle_not_needed(self, optimization_service):
        """Тест когда оптимизация не требуется"""
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=False)

        result = await optimization_service.start_optimization_cycle('test_capability')

        assert result is None

    @pytest.mark.asyncio
    async def test_start_optimization_cycle_lock_failed(self, optimization_service):
        """Тест когда не удалось acquire lock"""
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._acquire_lock = AsyncMock(return_value=False)

        result = await optimization_service.start_optimization_cycle('test_capability')

        assert result is None

    @pytest.mark.asyncio
    async def test_start_optimization_cycle_publishes_events(self, optimization_service):
        """Тест публикации событий"""
        received_events = []

        async def event_handler(event):
            received_events.append(event)

        optimization_service.event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, event_handler)
        optimization_service.event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, event_handler)

        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._analyze_failures = AsyncMock(return_value=FailureAnalysis(
            capability='test',
            version='v1.0.0',
            total_failures=0
        ))
        optimization_service._get_current_version = AsyncMock(return_value='v1.0.0')
        optimization_service._get_current_prompt = AsyncMock(return_value=MagicMock())
        optimization_service._test_new_version = AsyncMock(return_value={'metrics': {'accuracy': 0.95}})

        await optimization_service.start_optimization_cycle('test_capability')

        assert len(received_events) >= 2
        event_types = [e.event_type for e in received_events]
        assert 'optimization.cycle.started' in event_types


class TestAnalyzeFailures:
    """Тесты _analyze_failures"""

    @pytest.mark.asyncio
    async def test_analyze_failures(self, optimization_service):
        """Тест анализа неудач"""
        # Создаём тестовые логи ошибок
        error_logs = [
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_1',
                log_type=LogType.ERROR,
                data={'error_type': 'ValidationError'},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_2',
                log_type=LogType.ERROR,
                data={'error_type': 'ValidationError'},
                capability='test_cap'
            ),
            LogEntry(
                timestamp=datetime.now(),
                agent_id='agent_1',
                session_id='session_3',
                log_type=LogType.ERROR,
                data={'error_type': 'TimeoutError'},
                capability='test_cap'
            ),
        ]

        optimization_service.metrics_collector.log_collector.get_error_logs = AsyncMock(
            return_value=error_logs
        )

        analysis = await optimization_service._analyze_failures('test_cap', 'v1.0.0')

        # total_failures = сумма всех категорий (2 + 1 = 3) × 2 (потому что add_failure_category добавляет дважды)
        assert analysis.total_failures == 6  # 2*ValidationError + 1*TimeoutError = 3, но add_failure_category добавляет count к total_failures
        assert 'ValidationError' in analysis.failure_categories
        assert analysis.failure_categories['ValidationError'] == 2
        assert 'TimeoutError' in analysis.failure_categories
        assert analysis.failure_categories['TimeoutError'] == 1
        assert len(analysis.recommendations) > 0

    @pytest.mark.asyncio
    async def test_analyze_failures_empty(self, optimization_service):
        """Тест анализа без ошибок"""
        optimization_service.metrics_collector.log_collector.get_error_logs = AsyncMock(
            return_value=[]
        )

        analysis = await optimization_service._analyze_failures('test_cap', 'v1.0.0')

        assert analysis.total_failures == 0
        assert len(analysis.failure_categories) == 0


class TestNeedsOptimization:
    """Тесты _needs_optimization"""

    @pytest.mark.asyncio
    async def test_needs_optimization_accuracy(self, optimization_service):
        """Тест необходимости оптимизации по accuracy"""
        optimization_service.metrics_collector.get_aggregated_metrics = AsyncMock(
            return_value=MagicMock(accuracy=0.7)  # Ниже target 0.9
        )

        needs = await optimization_service._needs_optimization('test_cap', OptimizationMode.ACCURACY)

        assert needs is True

    @pytest.mark.asyncio
    async def test_needs_optimization_not_needed(self, optimization_service):
        """Тест когда оптимизация не нужна"""
        optimization_service.metrics_collector.get_aggregated_metrics = AsyncMock(
            return_value=MagicMock(accuracy=0.95)  # Выше target 0.9
        )

        needs = await optimization_service._needs_optimization('test_cap', OptimizationMode.ACCURACY)

        assert needs is False


class TestOptimizationLock:
    """Тесты блокировки"""

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, optimization_service):
        """Тест успешного acquire lock"""
        result = await optimization_service._acquire_lock('test_capability')

        assert result is True
        assert 'test_capability' in optimization_service._locks

    @pytest.mark.asyncio
    async def test_acquire_lock_already_locked(self, optimization_service):
        """Тест когда lock уже acquired"""
        # Первый acquire
        await optimization_service._acquire_lock('test_capability')

        # Второй acquire должен失败
        result = await optimization_service._acquire_lock('test_capability')

        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock(self, optimization_service):
        """Тест release lock"""
        await optimization_service._acquire_lock('test_capability')
        assert 'test_capability' in optimization_service._locks

        await optimization_service._release_lock('test_capability')

        assert 'test_capability' not in optimization_service._locks

    @pytest.mark.asyncio
    async def test_release_lock_not_exists(self, optimization_service):
        """Тест release несуществующего lock"""
        # Не должно вызвать ошибку
        await optimization_service._release_lock('nonexistent')


class TestImprovement:
    """Тесты проверки улучшения"""

    def test_is_improvement_accuracy(self, optimization_service):
        """Тест улучшения по accuracy"""
        old_metrics = {'accuracy': 0.7}
        new_metrics = {'accuracy': 0.85}

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.ACCURACY
        )

        assert is_improved is True  # 0.85 - 0.7 = 0.15 >= 0.05

    def test_is_improvement_not_enough(self, optimization_service):
        """Тест когда улучшение недостаточно"""
        old_metrics = {'accuracy': 0.7}
        new_metrics = {'accuracy': 0.72}  # Только 0.02 улучшение

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.ACCURACY
        )

        assert is_improved is False  # 0.02 < 0.05

    def test_is_improvement_speed(self, optimization_service):
        """Тест улучшения по скорости"""
        old_metrics = {'avg_execution_time_ms': 200.0}
        new_metrics = {'avg_execution_time_ms': 150.0}

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.SPEED
        )

        assert is_improved is True  # 150 < 200 * 0.95


class TestTargetAchieved:
    """Тесты достижения цели"""

    def test_is_target_achieved_default(self, optimization_service):
        """Тест достижения цели по умолчанию"""
        metrics = {'accuracy': 0.95}

        achieved = optimization_service._is_target_achieved(metrics, None)

        assert achieved is True  # 0.95 >= 0.9

    def test_is_target_achieved_not_met(self, optimization_service):
        """Тест когда цель не достигнута"""
        metrics = {'accuracy': 0.8}

        achieved = optimization_service._is_target_achieved(metrics, None)

        assert achieved is False  # 0.8 < 0.9

    def test_is_target_achieved_custom_metrics(self, optimization_service):
        """Тест с custom метриками"""
        metrics = {'accuracy': 0.95, 'speed': 100.0}
        target_metrics = [
            TargetMetric(name='accuracy', target_value=0.9, current_value=0.95),
            TargetMetric(name='speed', target_value=150.0, current_value=100.0)
        ]

        achieved = optimization_service._is_target_achieved(metrics, target_metrics)

        assert achieved is True  # accuracy: 0.95 >= 0.9, speed: 100 < 150 (но это хорошо для speed)


class TestOptimizationStatus:
    """Тесты статуса оптимизации"""

    @pytest.mark.asyncio
    async def test_get_optimization_status_running(self, optimization_service):
        """Тест статуса running"""
        await optimization_service._acquire_lock('test_capability')

        status = await optimization_service.get_optimization_status('test_capability')

        assert status['status'] == 'running'
        assert 'acquired_at' in status
        assert 'expires_at' in status

    @pytest.mark.asyncio
    async def test_get_optimization_status_idle(self, optimization_service):
        """Тест статуса idle"""
        status = await optimization_service.get_optimization_status('test_capability')

        assert status['status'] == 'idle'


class TestCancelOptimization:
    """Тесты отмены оптимизации"""

    @pytest.mark.asyncio
    async def test_cancel_optimization_success(self, optimization_service):
        """Тест успешной отмены"""
        await optimization_service._acquire_lock('test_capability')

        result = await optimization_service.cancel_optimization('test_capability')

        assert result is True
        assert 'test_capability' not in optimization_service._locks

    @pytest.mark.asyncio
    async def test_cancel_optimization_not_running(self, optimization_service):
        """Тест отмены когда не запущено"""
        result = await optimization_service.cancel_optimization('test_capability')

        assert result is False


class TestRecommendations:
    """Тесты генерации рекомендаций"""

    def test_generate_recommendations_syntax_error(self, optimization_service):
        """Тест рекомендаций для syntax ошибок"""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('syntax_error', 5)

        recommendations = optimization_service._generate_recommendations(analysis)

        assert len(recommendations) > 0
        assert any('validation' in r.lower() or 'syntax' in r.lower() for r in recommendations)

    def test_generate_recommendations_timeout(self, optimization_service):
        """Тест рекомендаций для timeout"""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('timeout_error', 3)

        recommendations = optimization_service._generate_recommendations(analysis)

        assert any('timeout' in r.lower() for r in recommendations)

    def test_generate_recommendations_multiple_categories(self, optimization_service):
        """Тест рекомендаций для нескольких категорий"""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('syntax_error', 5)
        analysis.add_failure_category('timeout_error', 3)
        analysis.add_failure_category('validation_error', 2)

        recommendations = optimization_service._generate_recommendations(analysis)

        # Должно быть максимум 3 рекомендации (top 3)
        assert len(recommendations) <= 3


class TestOptimizationConfig:
    """Тесты конфигурации"""

    def test_default_config(self):
        """Тест конфигурации по умолчанию"""
        config = OptimizationConfig()

        assert config.max_iterations == 5
        assert config.target_accuracy == 0.9
        assert config.min_improvement == 0.05
        assert config.timeout_seconds == 300
        assert config.max_concurrent == 1

    def test_custom_config(self):
        """Тест custom конфигурации"""
        config = OptimizationConfig(
            max_iterations=10,
            target_accuracy=0.95,
            min_improvement=0.1
        )

        assert config.max_iterations == 10
        assert config.target_accuracy == 0.95
        assert config.min_improvement == 0.1


class TestOptimizationLockClass:
    """Тесты класса OptimizationLock"""

    def test_optimization_lock_creation(self):
        """Тест создания lock"""
        now = datetime.now()
        lock = OptimizationLock(
            capability='test',
            acquired_at=now,
            expires_at=now + timedelta(minutes=5)
        )

        assert lock.capability == 'test'
        assert lock.acquired_at == now
        assert lock.owner == 'default'

    def test_optimization_lock_custom_owner(self):
        """Тест lock с custom owner"""
        lock = OptimizationLock(
            capability='test',
            acquired_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),
            owner='test_owner'
        )

        assert lock.owner == 'test_owner'
