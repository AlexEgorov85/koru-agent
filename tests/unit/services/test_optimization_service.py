"""
Юнит-тесты для OptimizationService.

ПРИМЕЧАНИЕ: Тесты используют реальные объекты EventBus и AccuracyEvaluatorService.
Моки допускаются только для LLM и БД провайдеров.
"""
import pytest
import asyncio
from datetime import datetime, timedelta

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
from core.infrastructure.event_bus.event_bus import EventBus
from core.application.services.accuracy_evaluator import AccuracyEvaluatorService


class TestOptimizationConfig:
    """Тесты конфигурации оптимизации."""

    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = OptimizationConfig()

        assert config.max_iterations == 5
        assert config.target_accuracy == 0.9
        assert config.min_improvement == 0.05
        assert config.timeout_seconds == 300
        assert config.max_concurrent == 1

    def test_custom_config(self):
        """Тест custom конфигурации."""
        config = OptimizationConfig(
            max_iterations=10,
            target_accuracy=0.95,
            min_improvement=0.1
        )

        assert config.max_iterations == 10
        assert config.target_accuracy == 0.95
        assert config.min_improvement == 0.1


class TestOptimizationLockClass:
    """Тесты класса OptimizationLock."""

    def test_optimization_lock_creation(self):
        """Тест создания lock."""
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
        """Тест lock с custom owner."""
        lock = OptimizationLock(
            capability='test',
            acquired_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),
            owner='test_owner'
        )

        assert lock.owner == 'test_owner'


class TestOptimizationLockMethods:
    """Тесты методов блокировки."""

    @pytest.fixture
    def event_bus(self):
        """EventBus для тестов."""
        return EventBus()

    @pytest.fixture
    def accuracy_evaluator(self):
        """AccuracyEvaluatorService для тестов."""
        return AccuracyEvaluatorService()

    @pytest.fixture
    def optimization_service(self, event_bus, accuracy_evaluator):
        """OptimizationService с реальными зависимостями."""
        # Создаем сервис с None для сложных зависимостей
        # Методы будут переопределены в тестах
        service = OptimizationService(
            benchmark_service=None,
            prompt_generator=None,
            metrics_collector=None,
            event_bus=event_bus,
            config=OptimizationConfig(max_iterations=3, target_accuracy=0.9)
        )
        return service

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, optimization_service):
        """Тест успешного acquire lock."""
        result = await optimization_service._acquire_lock('test_capability')

        assert result is True
        assert 'test_capability' in optimization_service._locks

    @pytest.mark.asyncio
    async def test_acquire_lock_already_locked(self, optimization_service):
        """Тест когда lock уже acquired."""
        # Первый acquire
        await optimization_service._acquire_lock('test_capability')

        # Второй acquire должен fail
        result = await optimization_service._acquire_lock('test_capability')

        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock(self, optimization_service):
        """Тест release lock."""
        await optimization_service._acquire_lock('test_capability')
        assert 'test_capability' in optimization_service._locks

        await optimization_service._release_lock('test_capability')

        assert 'test_capability' not in optimization_service._locks

    @pytest.mark.asyncio
    async def test_release_lock_not_exists(self, optimization_service):
        """Тест release несуществующего lock."""
        # Не должно вызвать ошибку
        await optimization_service._release_lock('nonexistent')

    @pytest.mark.asyncio
    async def test_get_optimization_status_running(self, optimization_service):
        """Тест статуса running."""
        await optimization_service._acquire_lock('test_capability')

        status = await optimization_service.get_optimization_status('test_capability')

        assert status['status'] == 'running'
        assert 'acquired_at' in status
        assert 'expires_at' in status

    @pytest.mark.asyncio
    async def test_get_optimization_status_idle(self, optimization_service):
        """Тест статуса idle."""
        status = await optimization_service.get_optimization_status('test_capability')

        assert status['status'] == 'idle'

    @pytest.mark.asyncio
    async def test_cancel_optimization_success(self, optimization_service):
        """Тест успешной отмены."""
        await optimization_service._acquire_lock('test_capability')

        result = await optimization_service.cancel_optimization('test_capability')

        assert result is True
        assert 'test_capability' not in optimization_service._locks

    @pytest.mark.asyncio
    async def test_cancel_optimization_not_running(self, optimization_service):
        """Тест отмены когда не запущено."""
        result = await optimization_service.cancel_optimization('test_capability')

        assert result is False


class TestImprovement:
    """Тесты проверки улучшения."""

    @pytest.fixture
    def event_bus(self):
        """EventBus для тестов."""
        return EventBus()

    @pytest.fixture
    def optimization_service(self, event_bus):
        """OptimizationService для тестов."""
        return OptimizationService(
            benchmark_service=None,
            prompt_generator=None,
            metrics_collector=None,
            event_bus=event_bus,
            config=OptimizationConfig()
        )

    def test_is_improvement_accuracy(self, optimization_service):
        """Тест улучшения по accuracy."""
        old_metrics = {'accuracy': 0.7}
        new_metrics = {'accuracy': 0.85}

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.ACCURACY
        )

        assert is_improved is True  # 0.85 - 0.7 = 0.15 >= 0.05

    def test_is_improvement_not_enough(self, optimization_service):
        """Тест когда улучшение недостаточно."""
        old_metrics = {'accuracy': 0.7}
        new_metrics = {'accuracy': 0.72}  # Только 0.02 улучшение

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.ACCURACY
        )

        assert is_improved is False  # 0.02 < 0.05

    def test_is_improvement_speed(self, optimization_service):
        """Тест улучшения по скорости."""
        old_metrics = {'avg_execution_time_ms': 200.0}
        new_metrics = {'avg_execution_time_ms': 150.0}

        is_improved = optimization_service._is_improvement(
            old_metrics,
            new_metrics,
            OptimizationMode.SPEED
        )

        assert is_improved is True  # 150 < 200 * 0.95


class TestTargetAchieved:
    """Тесты достижения цели."""

    @pytest.fixture
    def event_bus(self):
        """EventBus для тестов."""
        return EventBus()

    @pytest.fixture
    def optimization_service(self, event_bus):
        """OptimizationService для тестов."""
        return OptimizationService(
            benchmark_service=None,
            prompt_generator=None,
            metrics_collector=None,
            event_bus=event_bus,
            config=OptimizationConfig()
        )

    def test_is_target_achieved_default(self, optimization_service):
        """Тест достижения цели по умолчанию."""
        metrics = {'accuracy': 0.95}

        achieved = optimization_service._is_target_achieved(metrics, None)

        assert achieved is True  # 0.95 >= 0.9

    def test_is_target_achieved_not_met(self, optimization_service):
        """Тест когда цель не достигнута."""
        metrics = {'accuracy': 0.8}

        achieved = optimization_service._is_target_achieved(metrics, None)

        assert achieved is False  # 0.8 < 0.9

    def test_is_target_achieved_custom_metrics(self, optimization_service):
        """Тест с custom метриками."""
        metrics = {'accuracy': 0.95, 'speed': 100.0}
        target_metrics = [
            TargetMetric(name='accuracy', target_value=0.9, current_value=0.95),
            TargetMetric(name='speed', target_value=150.0, current_value=100.0)
        ]

        achieved = optimization_service._is_target_achieved(metrics, target_metrics)

        # accuracy: 0.95 >= 0.9, speed: 100 < 150 (но это хорошо для speed)
        assert achieved is True


class TestRecommendations:
    """Тесты генерации рекомендаций."""

    @pytest.fixture
    def event_bus(self):
        """EventBus для тестов."""
        return EventBus()

    @pytest.fixture
    def optimization_service(self, event_bus):
        """OptimizationService для тестов."""
        return OptimizationService(
            benchmark_service=None,
            prompt_generator=None,
            metrics_collector=None,
            event_bus=event_bus,
            config=OptimizationConfig()
        )

    def test_generate_recommendations_syntax_error(self, optimization_service):
        """Тест рекомендаций для syntax ошибок."""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('syntax_error', 5)

        recommendations = optimization_service._generate_recommendations(analysis)

        assert len(recommendations) > 0
        assert any('validation' in r.lower() or 'syntax' in r.lower() for r in recommendations)

    def test_generate_recommendations_timeout(self, optimization_service):
        """Тест рекомендаций для timeout."""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('timeout_error', 3)

        recommendations = optimization_service._generate_recommendations(analysis)

        assert any('timeout' in r.lower() for r in recommendations)

    def test_generate_recommendations_multiple_categories(self, optimization_service):
        """Тест рекомендаций для нескольких категорий."""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')
        analysis.add_failure_category('syntax_error', 5)
        analysis.add_failure_category('timeout_error', 3)
        analysis.add_failure_category('validation_error', 2)

        recommendations = optimization_service._generate_recommendations(analysis)

        # Должно быть максимум 3 рекомендации (top 3)
        assert len(recommendations) <= 3


class TestFailureAnalysis:
    """Тесты анализа неудач."""

    def test_failure_analysis_creation(self):
        """Тест создания FailureAnalysis."""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0.0',
            total_failures=0
        )

        assert analysis.capability == 'test_capability'
        assert analysis.version == 'v1.0.0'
        assert analysis.total_failures == 0
        assert analysis.failure_categories == {}
        assert analysis.recommendations == []

    def test_failure_analysis_add_category(self):
        """Тест добавления категории неудач."""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')

        analysis.add_failure_category('validation_error', 3)

        assert 'validation_error' in analysis.failure_categories
        assert analysis.failure_categories['validation_error'] == 3
        assert analysis.total_failures == 3

    def test_failure_analysis_add_multiple_categories(self):
        """Тест добавления нескольких категорий."""
        analysis = FailureAnalysis(capability='test', version='v1.0.0')

        analysis.add_failure_category('validation_error', 3)
        analysis.add_failure_category('timeout_error', 2)

        assert analysis.total_failures == 5
        assert len(analysis.failure_categories) == 2


class TestOptimizationMode:
    """Тесты режимов оптимизации."""

    def test_optimization_mode_values(self):
        """Тест значений OptimizationMode."""
        assert OptimizationMode.ACCURACY.value == 'accuracy'
        assert OptimizationMode.SPEED.value == 'speed'
        assert OptimizationMode.BALANCED.value == 'balanced'


class TestOptimizationResult:
    """Тесты результата оптимизации."""

    def test_optimization_result_creation(self):
        """Тест создания OptimizationResult."""
        result = OptimizationResult(
            capability='test_capability',
            from_version='v1.0.0',
            to_version='v1.0.1',
            mode=OptimizationMode.ACCURACY,
            iterations=3,
            improvements={'accuracy': 0.15},
            target_achieved=True
        )

        assert result.capability == 'test_capability'
        assert result.from_version == 'v1.0.0'
        assert result.to_version == 'v1.0.1'
        assert result.mode == OptimizationMode.ACCURACY
        assert result.iterations == 3
        assert result.improvements == {'accuracy': 0.15}
        assert result.target_achieved is True
