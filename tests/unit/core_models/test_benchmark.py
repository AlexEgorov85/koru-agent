"""
Юнит-тесты для моделей бенчмарков.

ТЕСТЫ:
- test_benchmark_scenario_creation: создание сценария бенчмарка
- test_expected_output_validation: валидация ожидаемого вывода
- test_accuracy_evaluation_calculation: расчёт оценки точности
- test_version_comparison: сравнение версий
- test_failure_analysis: анализ неудач
- test_optimization_result: результат оптимизации
"""
import pytest
from datetime import datetime, timedelta
from core.components.services.benchmarks.benchmark_models import (
    EvaluationType,
    EvaluationCriterion,
    BenchmarkScenario,
    ExpectedOutput,
    ActualOutput,
    BenchmarkResult,
    AccuracyEvaluation,
    CriterionScore,
    VersionComparison,
    FailureAnalysis,
    TargetMetric,
    OptimizationMode,
    OptimizationResult,
    LogType,
    LogEntry,
)


class TestEvaluationCriterion:
    """Тесты для EvaluationCriterion"""

    def test_evaluation_criterion_creation(self):
        """Тест создания критерия оценки"""
        criterion = EvaluationCriterion(
            name='accuracy',
            evaluation_type=EvaluationType.EXACT_MATCH,
            weight=0.8,
            description='Точность совпадения',
            threshold=0.75
        )

        assert criterion.name == 'accuracy'
        assert criterion.evaluation_type == EvaluationType.EXACT_MATCH
        assert criterion.weight == 0.8
        assert criterion.description == 'Точность совпадения'
        assert criterion.threshold == 0.75

    def test_evaluation_criterion_default_values(self):
        """Тест значений по умолчанию"""
        criterion = EvaluationCriterion(
            name='test_criterion',
            evaluation_type=EvaluationType.SEMANTIC
        )

        assert criterion.weight == 1.0
        assert criterion.description == ''
        assert criterion.threshold == 0.8

    def test_evaluation_criterion_invalid_weight(self):
        """Тест невалидного веса"""
        with pytest.raises(ValueError, match="Вес критерия должен быть от 0.0 до 1.0"):
            EvaluationCriterion(
                name='test',
                evaluation_type=EvaluationType.EXACT_MATCH,
                weight=1.5
            )

    def test_evaluation_criterion_weight_zero(self):
        """Тест веса 0.0 (допустимо)"""
        criterion = EvaluationCriterion(
            name='test',
            evaluation_type=EvaluationType.EXACT_MATCH,
            weight=0.0
        )
        assert criterion.weight == 0.0


class TestCriterionScore:
    """Тесты для CriterionScore"""

    def test_criterion_score_creation(self):
        """Тест создания оценки по критерию"""
        criterion = EvaluationCriterion(
            name='accuracy',
            evaluation_type=EvaluationType.EXACT_MATCH,
            threshold=0.75
        )
        score = CriterionScore(
            criterion=criterion,
            score=0.85,
            details='Хорошее совпадение'
        )

        assert score.criterion == criterion
        assert score.score == 0.85
        assert score.passed is True  # 0.85 >= 0.75
        assert score.details == 'Хорошее совпадение'

    def test_criterion_score_failed(self):
        """Тест непройденного порога"""
        criterion = EvaluationCriterion(
            name='accuracy',
            evaluation_type=EvaluationType.EXACT_MATCH,
            threshold=0.75
        )
        score = CriterionScore(
            criterion=criterion,
            score=0.60
        )

        assert score.passed is False  # 0.60 < 0.75

    def test_criterion_score_invalid_value(self):
        """Тест невалидной оценки"""
        criterion = EvaluationCriterion(
            name='test',
            evaluation_type=EvaluationType.EXACT_MATCH
        )
        with pytest.raises(ValueError, match="Оценка должна быть от 0.0 до 1.0"):
            CriterionScore(
                criterion=criterion,
                score=1.5
            )


class TestExpectedOutput:
    """Тесты для ExpectedOutput"""

    def test_expected_output_creation(self):
        """Тест создания ожидаемого вывода"""
        criterion = EvaluationCriterion(
            name='accuracy',
            evaluation_type=EvaluationType.EXACT_MATCH
        )
        output = ExpectedOutput(
            content={'result': 'expected'},
            schema={'type': 'object'},
            criteria=[criterion],
            metadata={'source': 'test'}
        )

        assert output.content == {'result': 'expected'}
        assert output.schema == {'type': 'object'}
        assert len(output.criteria) == 1
        assert output.metadata == {'source': 'test'}

    def test_expected_output_add_criterion(self):
        """Тест добавления критерия"""
        output = ExpectedOutput(content='test')
        criterion = EvaluationCriterion(
            name='new_criterion',
            evaluation_type=EvaluationType.SEMANTIC
        )

        output.add_criterion(criterion)

        assert len(output.criteria) == 1
        assert output.criteria[0].name == 'new_criterion'


class TestActualOutput:
    """Тесты для ActualOutput"""

    def test_actual_output_creation(self):
        """Тест создания фактического вывода"""
        output = ActualOutput(
            content={'result': 'actual'},
            execution_time_ms=150.5,
            tokens_used=500,
            metadata={'model': 'gpt-4'}
        )

        assert output.content == {'result': 'actual'}
        assert output.execution_time_ms == 150.5
        assert output.tokens_used == 500
        assert output.metadata == {'model': 'gpt-4'}

    def test_actual_output_default_values(self):
        """Тест значений по умолчанию"""
        output = ActualOutput(content='test')

        assert output.execution_time_ms == 0.0
        assert output.tokens_used == 0
        assert output.metadata == {}


class TestBenchmarkScenario:
    """Тесты для BenchmarkScenario"""

    def test_benchmark_scenario_creation(self):
        """Тест создания сценария бенчмарка"""
        expected_output = ExpectedOutput(content='expected')
        scenario = BenchmarkScenario(
            id='scenario_001',
            name='Тестовый сценарий',
            description='Описание сценария',
            goal='Выполни тестовое задание',
            expected_output=expected_output,
            timeout_seconds=120,
            metadata={'category': 'test'}
        )

        assert scenario.id == 'scenario_001'
        assert scenario.name == 'Тестовый сценарий'
        assert scenario.description == 'Описание сценария'
        assert scenario.goal == 'Выполни тестовое задание'
        assert scenario.timeout_seconds == 120
        assert scenario.metadata == {'category': 'test'}

    def test_benchmark_scenario_empty_id(self):
        """Тест пустого ID"""
        with pytest.raises(ValueError, match="ID сценария не может быть пустым"):
            BenchmarkScenario(
                id='',
                name='test',
                description='test',
                goal='test',
                expected_output=ExpectedOutput(content='test')
            )

    def test_benchmark_scenario_empty_goal(self):
        """Тест пустой цели"""
        with pytest.raises(ValueError, match="Цель сценария не может быть пустой"):
            BenchmarkScenario(
                id='test_001',
                name='test',
                description='test',
                goal='',
                expected_output=ExpectedOutput(content='test')
            )

    def test_benchmark_scenario_add_criterion(self):
        """Тест добавления критерия в сценарий"""
        scenario = BenchmarkScenario(
            id='test_001',
            name='test',
            description='test',
            goal='test goal',
            expected_output=ExpectedOutput(content='expected')
        )

        criterion = EvaluationCriterion(
            name='test_criterion',
            evaluation_type=EvaluationType.EXACT_MATCH
        )
        scenario.add_criterion(criterion)

        assert len(scenario.criteria) == 1
        assert len(scenario.expected_output.criteria) == 1


class TestBenchmarkResult:
    """Тесты для BenchmarkResult"""

    def test_benchmark_result_creation(self):
        """Тест создания результата бенчмарка"""
        result = BenchmarkResult(
            scenario_id='scenario_001',
            versions={'capability_1': 'v1.0'},
            success=True,
            execution_time_ms=200.0,
            tokens_used=600
        )

        assert result.scenario_id == 'scenario_001'
        assert result.versions == {'capability_1': 'v1.0'}
        assert result.success is True
        assert result.execution_time_ms == 200.0
        assert result.tokens_used == 600

    def test_benchmark_result_calculate_overall_score(self):
        """Тест расчёта общей оценки"""
        result = BenchmarkResult(
            scenario_id='test_001',
            versions={'cap': 'v1'}
        )

        # Добавляем оценки
        criterion1 = EvaluationCriterion(name='accuracy', evaluation_type=EvaluationType.EXACT_MATCH, weight=0.7)
        criterion2 = EvaluationCriterion(name='coverage', evaluation_type=EvaluationType.COVERAGE, weight=0.3)

        result.scores = [
            CriterionScore(criterion=criterion1, score=0.9),
            CriterionScore(criterion=criterion2, score=0.8)
        ]

        overall = result.calculate_overall_score()

        # (0.9 * 0.7 + 0.8 * 0.3) / (0.7 + 0.3) = (0.63 + 0.24) / 1.0 = 0.87
        assert overall == pytest.approx(0.87)
        assert result.overall_score == pytest.approx(0.87)

    def test_benchmark_result_all_criteria_passed(self):
        """Тест прохождения всех критериев"""
        result = BenchmarkResult(
            scenario_id='test_001',
            versions={'cap': 'v1'}
        )

        criterion = EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH, threshold=0.7)
        result.scores = [
            CriterionScore(criterion=criterion, score=0.8, passed=True),
            CriterionScore(criterion=criterion, score=0.75, passed=True)
        ]

        assert result.all_criteria_passed() is True

    def test_benchmark_result_some_criteria_failed(self):
        """Тест провала некоторых критериев"""
        result = BenchmarkResult(
            scenario_id='test_001',
            versions={'cap': 'v1'}
        )

        criterion = EvaluationCriterion(name='test', evaluation_type=EvaluationType.EXACT_MATCH, threshold=0.7)
        result.scores = [
            CriterionScore(criterion=criterion, score=0.8, passed=True),
            CriterionScore(criterion=criterion, score=0.5, passed=False)
        ]

        assert result.all_criteria_passed() is False

    def test_benchmark_result_to_dict(self):
        """Тест сериализации в словарь"""
        result = BenchmarkResult(
            scenario_id='test_001',
            versions={'cap': 'v1'},
            success=True,
            overall_score=0.85,
            execution_time_ms=200.0,
            tokens_used=500
        )

        data = result.to_dict()

        assert data['scenario_id'] == 'test_001'
        assert data['success'] is True
        assert data['overall_score'] == 0.85
        assert 'timestamp' in data


class TestAccuracyEvaluation:
    """Тесты для AccuracyEvaluation"""

    def test_accuracy_evaluation_empty_results(self):
        """Тест с пустыми результатами"""
        evaluation = AccuracyEvaluation.from_results(
            scenario_id='test_001',
            results=[]
        )

        assert evaluation.scenario_id == 'test_001'
        assert evaluation.total_runs == 0
        assert evaluation.accuracy == 0.0

    def test_accuracy_evaluation_calculation(self):
        """Тест расчёта оценки точности"""
        results = [
            BenchmarkResult(
                scenario_id='test_001',
                versions={'cap': 'v1'},
                success=True,
                execution_time_ms=100.0,
                tokens_used=500
            ),
            BenchmarkResult(
                scenario_id='test_001',
                versions={'cap': 'v1'},
                success=True,
                execution_time_ms=150.0,
                tokens_used=600
            ),
            BenchmarkResult(
                scenario_id='test_001',
                versions={'cap': 'v1'},
                success=False,
                execution_time_ms=200.0,
                tokens_used=400
            ),
        ]

        evaluation = AccuracyEvaluation.from_results(
            scenario_id='test_001',
            results=results
        )

        assert evaluation.total_runs == 3
        assert evaluation.successful_runs == 2
        assert evaluation.accuracy == pytest.approx(2/3, rel=1e-5)
        assert evaluation.avg_execution_time_ms == pytest.approx(150.0)
        assert evaluation.avg_tokens_used == pytest.approx(500.0)

    def test_accuracy_evaluation_scores_by_criterion(self):
        """Тест сбора оценок по критериям"""
        criterion = EvaluationCriterion(name='accuracy', evaluation_type=EvaluationType.EXACT_MATCH)

        results = [
            BenchmarkResult(
                scenario_id='test_001',
                versions={'cap': 'v1'},
                success=True,
                scores=[CriterionScore(criterion=criterion, score=0.9)]
            ),
            BenchmarkResult(
                scenario_id='test_001',
                versions={'cap': 'v1'},
                success=True,
                scores=[CriterionScore(criterion=criterion, score=0.8)]
            ),
        ]

        evaluation = AccuracyEvaluation.from_results(
            scenario_id='test_001',
            results=results
        )

        assert 'accuracy' in evaluation.scores_by_criterion
        assert evaluation.scores_by_criterion['accuracy'] == [0.9, 0.8]


class TestVersionComparison:
    """Тесты для VersionComparison"""

    def test_version_comparison_creation(self):
        """Тест создания сравнения версий"""
        comparison = VersionComparison(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            metrics_a={'accuracy': 0.8},
            metrics_b={'accuracy': 0.9}
        )

        assert comparison.capability == 'test_capability'
        assert comparison.version_a == 'v1.0'
        assert comparison.version_b == 'v2.0'

    def test_version_comparison_calculate_improvement(self):
        """Тест расчёта улучшения"""
        comparison = VersionComparison(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            metrics_a={'accuracy': 0.8},
            metrics_b={'accuracy': 0.9}
        )

        improvement = comparison.calculate_improvement('accuracy')

        # ((0.9 - 0.8) / 0.8) * 100 = 12.5%
        assert improvement == pytest.approx(12.5)
        assert comparison.winner == 'v2.0'

    def test_version_comparison_no_improvement(self):
        """Тест отсутствия улучшения"""
        comparison = VersionComparison(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            metrics_a={'accuracy': 0.9},
            metrics_b={'accuracy': 0.8}
        )

        comparison.calculate_improvement('accuracy')

        assert comparison.winner == 'v1.0'
        assert comparison.improvement < 0

    def test_version_comparison_equal_versions(self):
        """Тест равных версий"""
        comparison = VersionComparison(
            capability='test_capability',
            version_a='v1.0',
            version_b='v2.0',
            metrics_a={'accuracy': 0.8},
            metrics_b={'accuracy': 0.8}
        )

        comparison.calculate_improvement('accuracy')

        assert comparison.winner is None
        assert comparison.improvement == 0.0


class TestFailureAnalysis:
    """Тесты для FailureAnalysis"""

    def test_failure_analysis_creation(self):
        """Тест создания анализа неудач"""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0'
        )

        assert analysis.capability == 'test_capability'
        assert analysis.version == 'v1.0'
        assert analysis.total_failures == 0

    def test_failure_analysis_add_category(self):
        """Тест добавления категории ошибки"""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0'
        )

        analysis.add_failure_category('syntax_error', 2)
        analysis.add_failure_category('logic_error', 3)

        assert analysis.total_failures == 5
        assert analysis.failure_categories['syntax_error'] == 2
        assert analysis.failure_categories['logic_error'] == 3

    def test_failure_analysis_add_pattern(self):
        """Тест добавления паттерна"""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0'
        )

        analysis.add_pattern('Missing required field')
        analysis.add_pattern('Invalid JSON format')

        assert len(analysis.common_patterns) == 2
        assert 'Missing required field' in analysis.common_patterns

    def test_failure_analysis_add_recommendation(self):
        """Тест добавления рекомендации"""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0'
        )

        analysis.add_recommendation('Improve input validation')
        analysis.add_recommendation('Add error handling')

        assert len(analysis.recommendations) == 2

    def test_failure_analysis_get_top_categories(self):
        """Тест получения топ категорий"""
        analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0'
        )

        analysis.add_failure_category('syntax_error', 5)
        analysis.add_failure_category('logic_error', 3)
        analysis.add_failure_category('timeout', 1)

        top_categories = analysis.get_top_failure_categories(limit=2)

        assert len(top_categories) == 2
        assert top_categories[0] == ('syntax_error', 5)
        assert top_categories[1] == ('logic_error', 3)


class TestTargetMetric:
    """Тесты для TargetMetric"""

    def test_target_metric_creation(self):
        """Тест создания целевой метрики"""
        metric = TargetMetric(
            name='accuracy',
            target_value=0.95,
            current_value=0.85,
            threshold=0.8,
            weight=1.0
        )

        assert metric.name == 'accuracy'
        assert metric.target_value == 0.95
        assert metric.current_value == 0.85
        assert metric.is_achieved() is False

    def test_target_metric_achieved(self):
        """Тест достижения цели"""
        metric = TargetMetric(
            name='accuracy',
            target_value=0.9,
            current_value=0.95
        )

        assert metric.is_achieved() is True

    def test_target_metric_progress(self):
        """Тест прогресса"""
        metric = TargetMetric(
            name='accuracy',
            target_value=1.0,
            current_value=0.75
        )

        assert metric.progress() == 0.75

    def test_target_metric_progress_capped(self):
        """Тест прогресса с ограничением"""
        metric = TargetMetric(
            name='accuracy',
            target_value=0.9,
            current_value=0.95
        )

        assert metric.progress() == 1.0  # Прогресс не может быть > 1.0


class TestOptimizationResult:
    """Тесты для OptimizationResult"""

    def test_optimization_result_creation(self):
        """Тест создания результата оптимизации"""
        result = OptimizationResult(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0',
            mode=OptimizationMode.ACCURACY,
            iterations=5
        )

        assert result.capability == 'test_capability'
        assert result.from_version == 'v1.0'
        assert result.to_version == 'v2.0'
        assert result.mode == OptimizationMode.ACCURACY
        assert result.iterations == 5

    def test_optimization_result_calculate_improvements(self):
        """Тест расчёта улучшений"""
        result = OptimizationResult(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0',
            mode=OptimizationMode.ACCURACY,
            initial_metrics={'accuracy': 0.8, 'speed': 100.0},
            final_metrics={'accuracy': 0.9, 'speed': 80.0}
        )

        improvements = result.calculate_improvements()

        assert improvements['accuracy'] == pytest.approx(12.5)  # ((0.9-0.8)/0.8)*100
        assert improvements['speed'] == pytest.approx(-20.0)  # ((80-100)/100)*100

    def test_optimization_result_to_dict(self):
        """Тест сериализации в словарь"""
        result = OptimizationResult(
            capability='test_capability',
            from_version='v1.0',
            to_version='v2.0',
            mode=OptimizationMode.BALANCED,
            target_achieved=True
        )

        data = result.to_dict()

        assert data['capability'] == 'test_capability'
        assert data['mode'] == 'balanced'
        assert data['target_achieved'] is True
        assert 'timestamp' in data


class TestLogEntry:
    """Тесты для LogEntry"""

    def test_log_entry_creation(self):
        """Тест создания записи лога"""
        timestamp = datetime(2026, 2, 18, 10, 0, 0)
        entry = LogEntry(
            timestamp=timestamp,
            agent_id='agent_1',
            session_id='session_123',
            log_type=LogType.CAPABILITY_SELECTION,
            data={'capability': 'test_cap', 'reasoning': 'test'},
            correlation_id='corr_456',
            capability='test_capability',
            version='v1.0'
        )

        assert entry.agent_id == 'agent_1'
        assert entry.session_id == 'session_123'
        assert entry.log_type == LogType.CAPABILITY_SELECTION
        assert entry.correlation_id == 'corr_456'
        assert entry.capability == 'test_capability'
        assert entry.version == 'v1.0'

    def test_log_entry_to_dict(self):
        """Тест сериализации в словарь"""
        timestamp = datetime(2026, 2, 18, 10, 0, 0)
        entry = LogEntry(
            timestamp=timestamp,
            agent_id='agent_1',
            session_id='session_123',
            log_type=LogType.ERROR,
            data={'error': 'test error'}
        )

        data = entry.to_dict()

        assert data['agent_id'] == 'agent_1'
        assert data['session_id'] == 'session_123'
        assert data['log_type'] == 'error'
        assert data['timestamp'] == '2026-02-18T10:00:00'

    def test_log_entry_from_dict(self):
        """Тест десериализации из словаря"""
        data = {
            'timestamp': '2026-02-18T10:00:00',
            'agent_id': 'agent_1',
            'session_id': 'session_123',
            'log_type': 'benchmark',
            'data': {'scenario_id': 'test_001'},
            'correlation_id': 'corr_456',
            'capability': 'test_cap',
            'version': 'v1.0'
        }

        entry = LogEntry.from_dict(data)

        assert entry.agent_id == 'agent_1'
        assert entry.session_id == 'session_123'
        assert entry.log_type == LogType.BENCHMARK
        assert entry.correlation_id == 'corr_456'

    def test_log_entry_roundtrip(self):
        """Тест круговой сериализации"""
        original = LogEntry(
            timestamp=datetime(2026, 2, 18, 10, 0, 0),
            agent_id='agent_1',
            session_id='session_123',
            log_type=LogType.OPTIMIZATION,
            data={'iteration': 5},
            capability='test_cap',
            version='v2.0'
        )

        data = original.to_dict()
        restored = LogEntry.from_dict(data)

        assert restored.agent_id == original.agent_id
        assert restored.session_id == original.session_id
        assert restored.log_type == original.log_type
        assert restored.data == original.data


class TestLogType:
    """Тесты для Enum LogType"""

    def test_log_type_values(self):
        """Тест значений Enum"""
        assert LogType.CAPABILITY_SELECTION.value == 'capability_selection'
        assert LogType.ERROR.value == 'error'
        assert LogType.BENCHMARK.value == 'benchmark'
        assert LogType.OPTIMIZATION.value == 'optimization'

    def test_log_type_from_string(self):
        """Тест создания из строки"""
        assert LogType('capability_selection') == LogType.CAPABILITY_SELECTION
        assert LogType('error') == LogType.ERROR
        assert LogType('benchmark') == LogType.BENCHMARK


class TestOptimizationMode:
    """Тесты для Enum OptimizationMode"""

    def test_optimization_mode_values(self):
        """Тест значений Enum"""
        assert OptimizationMode.ACCURACY.value == 'accuracy'
        assert OptimizationMode.SPEED.value == 'speed'
        assert OptimizationMode.TOKENS.value == 'tokens'
        assert OptimizationMode.BALANCED.value == 'balanced'


class TestEvaluationType:
    """Тесты для Enum EvaluationType"""

    def test_evaluation_type_values(self):
        """Тест значений Enum"""
        assert EvaluationType.EXACT_MATCH.value == 'exact_match'
        assert EvaluationType.SEMANTIC.value == 'semantic'
        assert EvaluationType.COVERAGE.value == 'coverage'
        assert EvaluationType.CUSTOM.value == 'custom'
