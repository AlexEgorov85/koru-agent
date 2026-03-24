"""
Тесты для Evaluator.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.models.data.benchmark import BenchmarkRunResult, EvaluationResult
from core.application.components.optimization.evaluator import Evaluator, EvaluationConfig


class TestEvaluator:
    """Тесты для Evaluator"""

    @pytest.fixture
    def event_bus(self):
        """Mock event bus"""
        mock = AsyncMock()
        mock.publish = AsyncMock()
        return mock

    @pytest.fixture
    def evaluator(self, event_bus):
        """Создание evaluator"""
        return Evaluator(event_bus)

    def test_calculate_success_rate(self, evaluator):
        """Расчёт success rate"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=True),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=False),
            BenchmarkRunResult(version_id="v1", scenario_id="s4", success=True),
        ]

        success_rate = evaluator._calculate_success_rate(results)

        assert success_rate == 0.75  # 3/4

    def test_calculate_success_rate_empty(self, evaluator):
        """Расчёт success rate для пустого списка"""
        success_rate = evaluator._calculate_success_rate([])
        assert success_rate == 0.0

    def test_calculate_error_rate(self, evaluator):
        """Расчёт error rate"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True, error=None),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=False, error="Error 1"),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=True, error=None),
            BenchmarkRunResult(version_id="v1", scenario_id="s4", success=False, error="Error 2"),
        ]

        error_rate = evaluator._calculate_error_rate(results)

        assert error_rate == 0.5  # 2/4

    def test_calculate_avg_latency(self, evaluator):
        """Расчёт средней latency"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True, execution_time_ms=100),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=True, execution_time_ms=200),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=True, execution_time_ms=300),
        ]

        avg_latency = evaluator._calculate_avg_latency(results)

        assert avg_latency == 200.0  # (100+200+300)/3

    def test_evaluate(self, evaluator):
        """Полная оценка версии"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True, execution_time_ms=100),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=True, execution_time_ms=200),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=False, error="Error", execution_time_ms=150),
        ]

        evaluation = evaluator.evaluate("v1", results)

        assert evaluation.version_id == "v1"
        assert evaluation.success_rate == 2/3  # ~0.67
        assert evaluation.error_rate == 1/3  # ~0.33
        assert evaluation.latency == 150.0  # (100+200+150)/3
        assert evaluation.score > 0  # Score рассчитан

    def test_evaluate_empty_results(self, evaluator):
        """Оценка пустых результатов"""
        evaluation = evaluator.evaluate("v1", [])

        assert evaluation.version_id == "v1"
        assert evaluation.success_rate == 0.0
        assert evaluation.score == 0.0

    def test_select_best(self, evaluator):
        """Выбор лучшей версии"""
        evaluations = [
            EvaluationResult(version_id="v1", success_rate=0.7, score=0.65),
            EvaluationResult(version_id="v2", success_rate=0.85, score=0.80),
            EvaluationResult(version_id="v3", success_rate=0.75, score=0.70),
        ]

        best = evaluator.select_best(evaluations)

        assert best is not None
        assert best.version_id == "v2"
        assert best.score == 0.80

    def test_select_best_empty(self, evaluator):
        """Выбор из пустого списка"""
        best = evaluator.select_best([])
        assert best is None

    def test_compare(self, evaluator):
        """Сравнение двух оценок"""
        eval_a = EvaluationResult(
            version_id="v1",
            success_rate=0.7,
            execution_success=0.8,
            sql_validity=0.9,
            latency=100,
            error_rate=0.3,
            score=0.65
        )

        eval_b = EvaluationResult(
            version_id="v2",
            success_rate=0.85,
            execution_success=0.9,
            sql_validity=0.95,
            latency=120,
            error_rate=0.15,
            score=0.80
        )

        winner, improvements = evaluator.compare(eval_a, eval_b)

        assert winner == "B"  # B лучше
        assert improvements['success_rate'] > 0  # Улучшение по success_rate
        assert improvements['score'] > 0  # Улучшение по score

    def test_compare_tie(self, evaluator):
        """Сравнение с ничьей"""
        eval_a = EvaluationResult(version_id="v1", score=0.75)
        eval_b = EvaluationResult(version_id="v2", score=0.75)

        winner, _ = evaluator.compare(eval_a, eval_b)

        assert winner == "TIE"

    def test_get_metrics_report(self, evaluator):
        """Получение отчёта по метрикам"""
        evaluation = EvaluationResult(
            version_id="v1",
            success_rate=0.8,
            execution_success=0.9,
            sql_validity=0.95,
            latency=150,
            error_rate=0.2,
            score=0.75
        )

        report = evaluator.get_metrics_report(evaluation)

        assert report['version_id'] == "v1"
        assert 'metrics' in report
        assert 'score_breakdown' in report
        assert report['score'] == 0.75

    def test_calculate_correlation(self, evaluator):
        """Расчёт корреляции score с success_rate"""
        evaluations = [
            EvaluationResult(version_id="v1", success_rate=0.6, score=0.55),
            EvaluationResult(version_id="v2", success_rate=0.7, score=0.65),
            EvaluationResult(version_id="v3", success_rate=0.8, score=0.75),
            EvaluationResult(version_id="v4", success_rate=0.9, score=0.85),
        ]

        correlation_result = evaluator.calculate_correlation(evaluations)

        assert 'score_success_correlation' in correlation_result
        # Должна быть высокая положительная корреляция
        assert correlation_result['score_success_correlation'] > 0.8

    def test_sql_validity_with_sql_errors(self, evaluator):
        """Расчёт SQL validity с SQL ошибками"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=False, error="SQL syntax error"),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=True),
            BenchmarkRunResult(version_id="v1", scenario_id="s4", success=False, error="Table not found"),
        ]

        sql_validity = evaluator._calculate_sql_validity(results)

        # 2 SQL ошибки из 4 = 0.5 validity
        assert sql_validity == 0.5

    def test_sql_validity_no_sql_errors(self, evaluator):
        """Расчёт SQL validity без SQL ошибок"""
        results = [
            BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True),
            BenchmarkRunResult(version_id="v1", scenario_id="s2", success=False, error="Timeout"),
            BenchmarkRunResult(version_id="v1", scenario_id="s3", success=True),
        ]

        sql_validity = evaluator._calculate_sql_validity(results)

        assert sql_validity == 1.0  # Нет SQL ошибок


class TestEvaluationConfig:
    """Тесты для EvaluationConfig"""

    def test_default_weights(self):
        """Веса по умолчанию"""
        config = EvaluationConfig()

        assert config.success_rate_weight == 0.4
        assert config.execution_success_weight == 0.3
        assert config.sql_validity_weight == 0.2
        assert config.latency_weight == 0.1

        # Сумма весов должна быть 1.0 (с учётом floating point точности)
        total = (
            config.success_rate_weight +
            config.execution_success_weight +
            config.sql_validity_weight +
            config.latency_weight
        )
        assert abs(total - 1.0) < 0.0001

    def test_custom_weights(self):
        """Пользовательские веса"""
        config = EvaluationConfig(
            success_rate_weight=0.5,
            execution_success_weight=0.3,
            sql_validity_weight=0.1,
            latency_weight=0.1
        )

        assert config.success_rate_weight == 0.5
        assert config.min_success_rate == 0.8  # Default значение
