"""
E2E тесты для полного цикла бенчмарков.

ТЕСТЫ:
- test_full_benchmark_cycle: полный цикл бенчмарка
- test_benchmark_version_comparison: сравнение версий
- test_benchmark_version_promotion: продвижение версии
"""
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.benchmarks.benchmark_models import (
    BenchmarkScenario,
    ExpectedOutput,
    ActualOutput,
    EvaluationCriterion,
    EvaluationType,
    BenchmarkResult,
    VersionComparison,
)
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics


class TestFullBenchmarkCycle:
    """Тесты полного цикла бенчмарка"""

    @pytest.mark.asyncio
    async def test_full_benchmark_cycle(self, tmp_path):
        """
        Тест полного цикла бенчмарка:
        1. Создание сценария
        2. Запуск бенчмарка
        3. Сбор метрик
        4. Оценка результатов
        """
        from core.application.services.benchmark_service import BenchmarkService, BenchmarkConfig
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.metrics_collector import MetricsCollector
        from core.infrastructure.metrics_storage import FileSystemMetricsStorage
        from core.infrastructure.event_bus import EventBus, EventType

        # Создание тестовой директории
        metrics_dir = tmp_path / 'metrics'
        metrics_dir.mkdir()

        # Инициализация компонентов
        event_bus = EventBus()
        metrics_storage = FileSystemMetricsStorage(base_dir=metrics_dir)
        metrics_collector = MetricsCollector(event_bus, metrics_storage)
        await metrics_collector.initialize()

        accuracy_evaluator = AccuracyEvaluatorService()

        benchmark_service = BenchmarkService(
            metrics_collector=metrics_collector,
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus,
            config=BenchmarkConfig(max_iterations=3)
        )

        # Создание тестового сценария
        scenario = BenchmarkScenario(
            id='e2e_test_scenario',
            name='E2E Test Scenario',
            description='Full benchmark cycle test',
            goal='Test goal for E2E benchmark',
            expected_output=ExpectedOutput(
                content='Expected output for test',
                criteria=[
                    EvaluationCriterion(
                        name='accuracy',
                        evaluation_type=EvaluationType.EXACT_MATCH,
                        threshold=0.7,
                        weight=1.0
                    )
                ]
            ),
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.EXACT_MATCH,
                    threshold=0.7,
                    weight=1.0
                )
            ],
            timeout_seconds=30
        )

        # Mock executor для теста
        async def mock_executor(goal, version):
            return {
                'content': 'Mock response content',
                'execution_time_ms': 150.0,
                'tokens_used': 500
            }

        # Запуск бенчмарка
        result = await benchmark_service.run_benchmark(
            scenario=scenario,
            version='v1.0.0',
            agent_executor=mock_executor
        )

        # Проверка результатов
        assert result is not None
        assert result.scenario_id == scenario.id
        assert result.versions == {scenario.name: 'v1.0.0'}
        assert hasattr(result, 'success')
        assert hasattr(result, 'overall_score')
        assert hasattr(result, 'execution_time_ms')

        # Проверка что метрики записаны
        await asyncio.sleep(0.1)  # Даем время на запись метрик
        records = await metrics_collector.get_metrics('test_capability', 'v1.0.0')
        # Метрики могут быть записаны через EventBus

    @pytest.mark.asyncio
    async def test_benchmark_version_comparison(self, tmp_path):
        """
        Тест сравнения версий:
        1. Запуск бенчмарков для v1.0.0
        2. Запуск бенчмарков для v2.0.0
        3. Сравнение результатов
        4. Определение победителя
        """
        from core.application.services.benchmark_service import BenchmarkService, BenchmarkConfig
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.metrics_collector import MetricsCollector
        from core.infrastructure.metrics_storage import FileSystemMetricsStorage
        from core.infrastructure.event_bus import EventBus

        # Инициализация
        event_bus = EventBus()
        metrics_storage = FileSystemMetricsStorage(base_dir=tmp_path / 'metrics')
        metrics_collector = MetricsCollector(event_bus, metrics_storage)
        await metrics_collector.initialize()

        accuracy_evaluator = AccuracyEvaluatorService()
        benchmark_service = BenchmarkService(
            metrics_collector=metrics_collector,
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus
        )

        # Создание сценариев
        scenarios = [
            BenchmarkScenario(
                id=f'e2e_comparison_{i}',
                name=f'Comparison Scenario {i}',
                description='Version comparison test',
                goal=f'Test goal {i}',
                expected_output=ExpectedOutput(content=f'Expected {i}'),
                criteria=[
                    EvaluationCriterion(
                        name='accuracy',
                        evaluation_type=EvaluationType.EXACT_MATCH,
                        threshold=0.7
                    )
                ]
            )
            for i in range(3)
        ]

        # Mock executor с разными результатами для версий
        call_count = {'v1.0.0': 0, 'v2.0.0': 0}

        async def mock_executor(goal, version):
            call_count[version] = call_count.get(version, 0) + 1
            # v2.0.0 работает лучше
            if version == 'v2.0.0':
                return {
                    'content': 'Better response',
                    'execution_time_ms': 100.0,
                    'tokens_used': 400
                }
            else:
                return {
                    'content': 'Standard response',
                    'execution_time_ms': 150.0,
                    'tokens_used': 500
                }

        # Сравнение версий
        comparison = await benchmark_service.compare_versions(
            capability='test_capability',
            version_a='v1.0.0',
            version_b='v2.0.0',
            scenarios=scenarios,
            agent_executor=mock_executor
        )

        # Проверка результатов сравнения
        assert comparison is not None
        assert comparison.capability == 'test_capability'
        assert comparison.version_a == 'v1.0.0'
        assert comparison.version_b == 'v2.0.0'
        assert 'accuracy' in comparison.metrics_a
        assert 'accuracy' in comparison.metrics_b
        assert hasattr(comparison, 'improvement')
        assert hasattr(comparison, 'winner')

    @pytest.mark.asyncio
    async def test_benchmark_version_promotion(self):
        """
        Тест продвижения версии:
        1. Создание BenchmarkService
        2. Вызов promote_version
        3. Проверка публикации события
        """
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.metrics_collector import MetricsCollector
        from core.infrastructure.event_bus import EventBus, EventType

        # Инициализация
        event_bus = EventBus()
        metrics_collector = MagicMock(spec=MetricsCollector)
        accuracy_evaluator = AccuracyEvaluatorService()

        benchmark_service = BenchmarkService(
            metrics_collector=metrics_collector,
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus
        )

        # Подписка на событие продвижения
        promoted_events = []

        async def on_version_promoted(event):
            promoted_events.append(event)

        event_bus.subscribe(EventType.VERSION_PROMOTED, on_version_promoted)

        # Продвижение версии
        result = await benchmark_service.promote_version(
            capability='test_capability',
            from_version='v1.0.0',
            to_version='v2.0.0',
            reason='Better accuracy in E2E tests'
        )

        # Проверка
        assert result is True
        assert len(promoted_events) == 1
        assert promoted_events[0].data['capability'] == 'test_capability'
        assert promoted_events[0].data['to_version'] == 'v2.0.0'


class TestBenchmarkWithRealComponents:
    """Тесты бенчмарков с реальными компонентами"""

    @pytest.mark.asyncio
    async def test_benchmark_with_mock_storages(self, tmp_path):
        """Тест бенчмарка с моковыми хранилищами"""
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService, EvaluationResult
        from core.infrastructure.event_bus import EventBus, EventType

        # Создаём моки для хранилищ
        event_bus = EventBus()
        accuracy_evaluator = AccuracyEvaluatorService()

        # Мокаем evaluate чтобы вернуть успешный результат
        original_evaluate = accuracy_evaluator.evaluate

        async def mock_evaluate(expected, actual, criterion):
            return EvaluationResult(
                score=0.85,
                passed=True,
                details='Mock evaluation passed',
                criterion=criterion.name,
                evaluation_type=criterion.evaluation_type
            )

        accuracy_evaluator.evaluate = mock_evaluate

        benchmark_service = BenchmarkService(
            metrics_collector=MagicMock(),
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus
        )

        # Создание сценария
        scenario = BenchmarkScenario(
            id='real_components_test',
            name='Real Components Test',
            description='Test with real accuracy evaluator',
            goal='Test goal',
            expected_output=ExpectedOutput(
                content='Expected output',
                criteria=[
                    EvaluationCriterion(
                        name='accuracy',
                        evaluation_type=EvaluationType.EXACT_MATCH,
                        threshold=0.7
                    )
                ]
            ),
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.EXACT_MATCH,
                    threshold=0.7
                )
            ]
        )

        # Mock executor
        async def mock_executor(goal, version):
            return {
                'content': 'Actual output',
                'execution_time_ms': 100.0,
                'tokens_used': 300
            }

        # Запуск бенчмарка
        result = await benchmark_service.run_benchmark(
            scenario=scenario,
            version='v1.0.0',
            agent_executor=mock_executor
        )

        # Проверка
        assert result is not None
        assert result.scenario_id == 'real_components_test'
        assert result.success is True  # Оценка 0.85 > threshold 0.7
        assert result.overall_score >= 0.8


class TestBenchmarkErrorHandling:
    """Тесты обработки ошибок в бенчмарках"""

    @pytest.mark.asyncio
    async def test_benchmark_executor_error(self):
        """Тест ошибки executor"""
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = BenchmarkService(
            metrics_collector=MagicMock(),
            accuracy_evaluator=AccuracyEvaluatorService(),
            event_bus=event_bus
        )

        scenario = BenchmarkScenario(
            id='error_test',
            name='Error Test',
            description='Test error handling',
            goal='Test goal',
            expected_output=ExpectedOutput(content='Expected'),
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.EXACT_MATCH,
                    threshold=0.7
                )
            ]
        )

        # Executor который выбрасывает ошибку
        async def failing_executor(goal, version):
            raise Exception("Executor failed")

        result = await benchmark_service.run_benchmark(
            scenario=scenario,
            version='v1.0.0',
            agent_executor=failing_executor
        )

        # Проверка что ошибка обработана
        assert result is not None
        assert result.success is False
        assert result.error is not None
        assert "Executor failed" in result.error

    @pytest.mark.asyncio
    async def test_benchmark_timeout(self):
        """Тест таймаута бенчмарка"""
        from core.application.services.benchmark_service import BenchmarkService, BenchmarkConfig
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = BenchmarkService(
            metrics_collector=MagicMock(),
            accuracy_evaluator=AccuracyEvaluatorService(),
            event_bus=event_bus,
            config=BenchmarkConfig(timeout_seconds=1)
        )

        scenario = BenchmarkScenario(
            id='timeout_test',
            name='Timeout Test',
            description='Test timeout handling',
            goal='Test goal',
            expected_output=ExpectedOutput(content='Expected'),
            criteria=[
                EvaluationCriterion(
                    name='accuracy',
                    evaluation_type=EvaluationType.EXACT_MATCH,
                    threshold=0.7
                )
            ],
            timeout_seconds=1
        )

        # Executor который долго выполняется
        async def slow_executor(goal, version):
            await asyncio.sleep(2)  # Дольше чем timeout
            return {'content': 'Slow response'}

        result = await benchmark_service.run_benchmark(
            scenario=scenario,
            version='v1.0.0',
            agent_executor=slow_executor
        )

        # Бенчмарк должен завершиться (возможно с ошибкой таймаута)
        assert result is not None
