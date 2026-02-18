"""
Юнит-тесты для BenchmarkService.

ТЕСТЫ:
- test_run_benchmark: запуск бенчмарка
- test_compare_versions: сравнение версий
- test_promote_version: продвижение версии
- test_auto_promote_if_better: автоматическое продвижение
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from core.models.data.benchmark import (
    BenchmarkScenario,
    BenchmarkResult,
    ExpectedOutput,
    ActualOutput,
    EvaluationCriterion,
    EvaluationType,
)
from core.application.services.benchmark_service import BenchmarkService, BenchmarkConfig
from core.application.services.accuracy_evaluator import AccuracyEvaluatorService, EvaluationResult
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.event_bus import EventBus, EventType


@pytest.fixture
def mock_metrics_collector():
    """Моковый MetricsCollector"""
    collector = AsyncMock(spec=MetricsCollector)
    collector.get_aggregated_metrics = AsyncMock(return_value=MagicMock())
    return collector


@pytest.fixture
def mock_accuracy_evaluator():
    """Моковый AccuracyEvaluator"""
    evaluator = AsyncMock(spec=AccuracyEvaluatorService)
    evaluator.evaluate = AsyncMock(return_value=EvaluationResult(
        score=0.9,
        passed=True,
        details="Good match",
        criterion='test',
        evaluation_type=EvaluationType.EXACT_MATCH
    ))
    return evaluator


@pytest.fixture
def event_bus():
    """EventBus для тестов"""
    return EventBus()


@pytest.fixture
def benchmark_service(mock_metrics_collector, mock_accuracy_evaluator, event_bus):
    """BenchmarkService для тестов"""
    return BenchmarkService(
        metrics_collector=mock_metrics_collector,
        accuracy_evaluator=mock_accuracy_evaluator,
        event_bus=event_bus,
        config=BenchmarkConfig(max_iterations=5)
    )


@pytest.fixture
def sample_scenario():
    """Тестовый сценарий"""
    return BenchmarkScenario(
        id='scenario_001',
        name='Test Scenario',
        description='Test description',
        goal='Test goal',
        expected_output=ExpectedOutput(
            content='Expected output',
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.EXACT_MATCH,
                    weight=1.0,
                    threshold=0.8
                )
            ]
        ),
        criteria=[
            EvaluationCriterion(
                name='accuracy',
                evaluation_type=EvaluationType.EXACT_MATCH,
                weight=1.0,
                threshold=0.8
            )
        ],
        timeout_seconds=30
    )


class TestRunBenchmark:
    """Тесты run_benchmark"""

    @pytest.mark.asyncio
    async def test_run_benchmark_success(self, benchmark_service, sample_scenario):
        """Тест успешного запуска бенчмарка"""
        result = await benchmark_service.run_benchmark(sample_scenario, 'v1.0')

        assert isinstance(result, BenchmarkResult)
        assert result.scenario_id == sample_scenario.id
        assert result.versions == {sample_scenario.name: 'v1.0'}
        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_benchmark_with_executor(self, benchmark_service, sample_scenario):
        """Тест запуска бенчмарка с executor"""
        async def mock_executor(goal, version):
            return {
                'content': 'Executor response',
                'execution_time_ms': 150.0,
                'tokens_used': 100
            }

        result = await benchmark_service.run_benchmark(sample_scenario, 'v1.0', mock_executor)

        assert result.actual_output is not None
        assert result.actual_output.content == 'Executor response'
        assert result.actual_output.execution_time_ms == 150.0
        assert result.actual_output.tokens_used == 100

    @pytest.mark.asyncio
    async def test_run_benchmark_failure(self, benchmark_service, sample_scenario):
        """Тест неудачного запуска бенчмарка"""
        async def failing_executor(goal, version):
            raise Exception("Test error")

        result = await benchmark_service.run_benchmark(sample_scenario, 'v1.0', failing_executor)

        assert result.success is False
        assert result.error == "Test error"

    @pytest.mark.asyncio
    async def test_run_benchmark_publishes_events(self, benchmark_service, sample_scenario):
        """Тест публикации событий"""
        received_events = []

        async def event_handler(event):
            received_events.append(event)

        benchmark_service.event_bus.subscribe(EventType.BENCHMARK_STARTED, event_handler)
        benchmark_service.event_bus.subscribe(EventType.BENCHMARK_COMPLETED, event_handler)

        await benchmark_service.run_benchmark(sample_scenario, 'v1.0')

        assert len(received_events) >= 2
        event_types = [e.event_type for e in received_events]
        assert 'benchmark.started' in event_types
        assert 'benchmark.completed' in event_types


class TestCompareVersions:
    """Тесты compare_versions"""

    @pytest.mark.asyncio
    async def test_compare_versions(self, benchmark_service, sample_scenario):
        """Тест сравнения версий"""
        comparison = await benchmark_service.compare_versions(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            scenarios=[sample_scenario]
        )

        assert comparison.capability == 'test_capability'
        assert comparison.version_a == 'v1.0'
        assert comparison.version_b == 'v2.0'
        assert 'accuracy' in comparison.metrics_a
        assert 'accuracy' in comparison.metrics_b

    @pytest.mark.asyncio
    async def test_compare_versions_multiple_scenarios(self, benchmark_service):
        """Тест сравнения по нескольким сценариям"""
        scenarios = [
            BenchmarkScenario(
                id=f'scenario_{i}',
                name=f'Scenario {i}',
                description='Test',
                goal='Test goal',
                expected_output=ExpectedOutput(content='Expected')
            )
            for i in range(3)
        ]

        comparison = await benchmark_service.compare_versions(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            scenarios=scenarios
        )

        # Метрики должны быть агрегированы по всем сценариям
        assert comparison.metrics_a['accuracy'] >= 0.0
        assert comparison.metrics_b['accuracy'] >= 0.0


class TestPromoteVersion:
    """Тесты promote_version"""

    @pytest.mark.asyncio
    async def test_promote_version_success(self, benchmark_service):
        """Тест успешного продвижения версии"""
        result = await benchmark_service.promote_version(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0',
            reason='Better accuracy'
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_promote_version_publishes_event(self, benchmark_service):
        """Тест публикации события при продвижении"""
        received_events = []

        async def event_handler(event):
            received_events.append(event)

        benchmark_service.event_bus.subscribe(EventType.VERSION_PROMOTED, event_handler)

        await benchmark_service.promote_version(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0'
        )

        assert len(received_events) == 1
        assert received_events[0].event_type == 'version.promoted'
        assert received_events[0].data['to_version'] == 'v2.0'

    @pytest.mark.asyncio
    async def test_promote_version_with_callback(self, benchmark_service):
        """Тест продвижения с callback"""
        callback_called = False

        async def mock_callback(capability, from_ver, to_ver):
            nonlocal callback_called
            callback_called = True

        benchmark_service.set_registry_callback(mock_callback)

        await benchmark_service.promote_version(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0'
        )

        assert callback_called is True


class TestRejectVersion:
    """Тесты reject_version"""

    @pytest.mark.asyncio
    async def test_reject_version(self, benchmark_service):
        """Тест отклонения версии"""
        result = await benchmark_service.reject_version(
            capability='test_capability',
            version='v2.0',
            reason='Poor performance'
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_reject_version_publishes_event(self, benchmark_service):
        """Тест публикации события при отклонении"""
        received_events = []

        async def event_handler(event):
            received_events.append(event)

        benchmark_service.event_bus.subscribe(EventType.VERSION_REJECTED, event_handler)

        await benchmark_service.reject_version(
            capability='test_capability',
            version='v2.0',
            reason='Test reason'
        )

        assert len(received_events) == 1
        assert received_events[0].event_type == 'version.rejected'


class TestAutoPromoteIfBetter:
    """Тесты auto_promote_if_better"""

    @pytest.mark.asyncio
    async def test_auto_promote_when_better(self, benchmark_service, sample_scenario):
        """Тест автоматического продвижения когда версия лучше"""
        # Мокаем compare_versions чтобы вернуть улучшение
        original_compare = benchmark_service.compare_versions

        async def mock_compare(cap, va, vb, scenarios, executor=None):
            from core.models.data.benchmark import VersionComparison
            comparison = VersionComparison(
                capability=cap,
                version_a=va,
                version_b=vb,
                metrics_a={'accuracy': 0.7},
                metrics_b={'accuracy': 0.9}
            )
            comparison.winner = vb
            comparison.improvement = 28.5  # 28.5% улучшение
            return comparison

        benchmark_service.compare_versions = mock_compare

        result = await benchmark_service.auto_promote_if_better(
            capability='test_capability',
            candidate_version='v2.0',
            current_version='v1.0',
            scenarios=[sample_scenario],
            metric_threshold=0.05  # 5% порог
        )

        assert result is True  # Версия должна быть продвинута

    @pytest.mark.asyncio
    async def test_auto_promote_when_not_better(self, benchmark_service, sample_scenario):
        """Тест когда версия не лучше"""
        async def mock_compare(cap, va, vb, scenarios, executor=None):
            from core.models.data.benchmark import VersionComparison
            comparison = VersionComparison(
                capability=cap,
                version_a=va,
                version_b=vb,
                metrics_a={'accuracy': 0.9},
                metrics_b={'accuracy': 0.85}
            )
            comparison.winner = va  # Старая версия лучше
            comparison.improvement = -5.5
            return comparison

        benchmark_service.compare_versions = mock_compare

        result = await benchmark_service.auto_promote_if_better(
            capability='test_capability',
            candidate_version='v2.0',
            current_version='v1.0',
            scenarios=[sample_scenario]
        )

        assert result is False  # Версия не должна быть продвинута


class TestAggregateMetrics:
    """Тесты агрегации метрик"""

    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, benchmark_service):
        """Тест агрегации метрик"""
        results = [
            BenchmarkResult(
                scenario_id='test',
                versions={'test': 'v1.0'},
                success=True,
                overall_score=0.9,
                execution_time_ms=100.0,
                tokens_used=50
            ),
            BenchmarkResult(
                scenario_id='test',
                versions={'test': 'v1.0'},
                success=False,
                overall_score=0.5,
                execution_time_ms=150.0,
                tokens_used=60
            ),
            BenchmarkResult(
                scenario_id='test',
                versions={'test': 'v1.0'},
                success=True,
                overall_score=0.8,
                execution_time_ms=120.0,
                tokens_used=55
            ),
        ]

        metrics = benchmark_service._aggregate_metrics(results)

        assert metrics['accuracy'] == pytest.approx(2/3, rel=1e-5)  # 2 из 3 успешных
        assert metrics['avg_execution_time_ms'] == pytest.approx(123.33, rel=1e-2)
        assert metrics['avg_tokens'] == 55
        assert metrics['avg_score'] == pytest.approx(0.733, rel=1e-2)


class TestCalculateOverallScore:
    """Тесты расчёта общей оценки"""

    def test_calculate_overall_score_single(self, benchmark_service):
        """Тест расчёта с одной оценкой"""
        from core.models.data.benchmark import CriterionScore

        scores = [
            CriterionScore(
                criterion=EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH, weight=1.0),
                score=0.8,
                passed=True
            )
        ]

        overall = benchmark_service._calculate_overall_score(scores)
        assert overall == 0.8

    def test_calculate_overall_score_weighted(self, benchmark_service):
        """Тест расчёта с весами"""
        from core.models.data.benchmark import CriterionScore

        scores = [
            CriterionScore(
                criterion=EvaluationCriterion(name='test1', evaluation_type=EvaluationType.EXACT_MATCH, weight=0.7),
                score=0.9,
                passed=True
            ),
            CriterionScore(
                criterion=EvaluationCriterion(name='test2', evaluation_type=EvaluationType.COVERAGE, weight=0.3),
                score=0.7,
                passed=True
            ),
        ]

        overall = benchmark_service._calculate_overall_score(scores)
        # (0.9 * 0.7 + 0.7 * 0.3) / 1.0 = 0.63 + 0.21 = 0.84
        assert overall == pytest.approx(0.84)

    def test_calculate_overall_score_empty(self, benchmark_service):
        """Тест с пустым списком"""
        overall = benchmark_service._calculate_overall_score([])
        assert overall == 0.0


class TestDetermineSuccess:
    """Тесты определения успешности"""

    def test_determine_success_all_passed(self, benchmark_service):
        """Тест когда все критерии пройдены"""
        from core.models.data.benchmark import CriterionScore

        scores = [
            CriterionScore(
                criterion=EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH),
                score=0.9,
                passed=True
            )
        ]

        scenario = BenchmarkScenario(
            id='test',
            name='Test',
            description='Test',
            goal='Test',
            expected_output=ExpectedOutput(content='test')
        )

        success = benchmark_service._determine_success(scores, 0.9, scenario)
        assert success is True

    def test_determine_success_high_score(self, benchmark_service):
        """Тест когда высокая общая оценка"""
        from core.models.data.benchmark import CriterionScore

        scores = [
            CriterionScore(
                criterion=EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH),
                score=0.85,
                passed=False  # Один критерий не пройден
            )
        ]

        scenario = BenchmarkScenario(
            id='test',
            name='Test',
            description='Test',
            goal='Test',
            expected_output=ExpectedOutput(content='test')
        )

        # Но общая оценка выше порога
        success = benchmark_service._determine_success(scores, 0.85, scenario)
        assert success is True  # 0.85 >= 0.8 threshold

    def test_determine_success_failure(self, benchmark_service):
        """Тест провала"""
        from core.models.data.benchmark import CriterionScore

        scores = [
            CriterionScore(
                criterion=EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH),
                score=0.5,
                passed=False
            )
        ]

        scenario = BenchmarkScenario(
            id='test',
            name='Test',
            description='Test',
            goal='Test',
            expected_output=ExpectedOutput(content='test')
        )

        success = benchmark_service._determine_success(scores, 0.5, scenario)
        assert success is False  # 0.5 < 0.8 threshold


class TestStatisticalSignificance:
    """Тесты статистической значимости"""

    def test_check_statistical_significance_significant(self, benchmark_service):
        """Тест значимой разницы"""
        results_a = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.5),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.5),
            BenchmarkResult(scenario_id='test', versions={}, success=False, overall_score=0.5),
        ]

        results_b = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.9),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.9),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.9),
        ]

        significant = benchmark_service._check_statistical_significance(results_a, results_b)
        assert significant is True  # 100% vs 33% = значимая разница

    def test_check_statistical_significance_not_significant(self, benchmark_service):
        """Тест незначимой разницы"""
        results_a = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
        ]

        results_b = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
        ]

        significant = benchmark_service._check_statistical_significance(results_a, results_b)
        assert significant is False  # Разница 0% < 10%

    def test_check_statistical_significance_insufficient_data(self, benchmark_service):
        """Тест недостаточного количества данных"""
        results_a = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.8),
        ]

        results_b = [
            BenchmarkResult(scenario_id='test', versions={}, success=True, overall_score=0.9),
        ]

        significant = benchmark_service._check_statistical_significance(results_a, results_b)
        assert significant is False  # Недостаточно данных (< 3)
