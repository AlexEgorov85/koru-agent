"""
Тесты для моделей данных оптимизации.
"""
import pytest
from datetime import datetime

from core.components.benchmarks.benchmark_models import (
    OptimizationSample,
    ScenarioType,
    PromptVersion,
    EvaluationResult,
    MutationType,
    BenchmarkDataset,
)


class TestOptimizationSample:
    """Тесты для OptimizationSample"""

    def test_create_success_sample(self):
        """Создание успешного образца"""
        sample = OptimizationSample(
            id="test-1",
            input="SELECT * FROM users",
            success=True,
            actual_output="Query executed"
        )

        assert sample.id == "test-1"
        assert sample.success is True
        assert sample.scenario_type == ScenarioType.EASY

    def test_create_failure_sample(self):
        """Создание образца с ошибкой"""
        sample = OptimizationSample(
            id="test-2",
            input="INVALID QUERY",
            success=False,
            error="Syntax error"
        )

        assert sample.success is False
        assert sample.error == "Syntax error"
        assert sample.scenario_type == ScenarioType.FAILURE

    def test_create_edge_sample(self):
        """Создание пограничного образца"""
        sample = OptimizationSample(
            id="test-3",
            input="Complex query",
            success=False,
            error=None
        )

        assert sample.success is False
        assert sample.error is None
        assert sample.scenario_type == ScenarioType.EDGE

    def test_to_dict(self):
        """Сериализация в словарь"""
        sample = OptimizationSample(
            id="test-4",
            input="Test input",
            success=True
        )

        data = sample.to_dict()

        assert data['id'] == "test-4"
        assert data['input'] == "Test input"
        assert data['success'] is True
        assert data['scenario_type'] == "easy"

    def test_from_dict(self):
        """Десериализация из словаря"""
        data = {
            'id': 'test-5',
            'input': 'Test input',
            'success': False,
            'error': 'Test error',
            'scenario_type': 'failure'
        }

        sample = OptimizationSample.from_dict(data)

        assert sample.id == "test-5"
        assert sample.success is False
        assert sample.error == "Test error"
        assert sample.scenario_type == ScenarioType.FAILURE


class TestPromptVersion:
    """Тесты для PromptVersion"""

    def test_create_version(self):
        """Создание версии промпта"""
        version = PromptVersion(
            id="v1",
            parent_id=None,
            capability="test_cap",
            prompt="Test prompt content"
        )

        assert version.id == "v1"
        assert version.parent_id is None
        assert version.status == "candidate"

    def test_create_version_with_parent(self):
        """Создание версии с родителем"""
        version = PromptVersion(
            id="v2",
            parent_id="v1",
            capability="test_cap",
            prompt="Improved prompt",
            mutation_type=MutationType.ADD_EXAMPLES
        )

        assert version.parent_id == "v1"
        assert version.mutation_type == MutationType.ADD_EXAMPLES

    def test_promote_version(self):
        """Продвижение версии"""
        version = PromptVersion(
            id="v1",
            parent_id=None,
            capability="test_cap",
            prompt="Test"
        )

        assert version.status == "candidate"
        version.promote()
        assert version.status == "active"

    def test_reject_version(self):
        """Отклонение версии"""
        version = PromptVersion(
            id="v1",
            parent_id=None,
            capability="test_cap",
            prompt="Test"
        )

        version.reject()
        assert version.status == "rejected"

    def test_invalid_status(self):
        """Проверка валидации статуса"""
        with pytest.raises(ValueError):
            PromptVersion(
                id="v1",
                parent_id=None,
                capability="test_cap",
                prompt="Test",
                status="invalid_status"
            )


class TestEvaluationResult:
    """Тесты для EvaluationResult"""

    def test_create_evaluation(self):
        """Создание оценки"""
        eval_result = EvaluationResult(
            version_id="v1",
            success_rate=0.85,
            sql_validity=0.95,
            execution_success=0.90,
            latency=150.0,
            error_rate=0.15
        )

        assert eval_result.version_id == "v1"
        assert eval_result.success_rate == 0.85

    def test_calculate_score(self):
        """Расчёт итогового score"""
        eval_result = EvaluationResult(
            version_id="v1",
            success_rate=0.8,
            sql_validity=1.0,
            execution_success=0.9,
            latency=100.0,
            error_rate=0.2
        )

        score = eval_result.calculate_score()

        # score = 0.8*0.4 + 0.9*0.3 + 1.0*0.2 - 0.1*0.1
        # score = 0.32 + 0.27 + 0.2 - 0.01 = 0.78
        assert abs(score - 0.78) < 0.01

    def test_calculate_score_with_high_latency(self):
        """Расчёт score с высокой latency"""
        eval_result = EvaluationResult(
            version_id="v1",
            success_rate=0.8,
            sql_validity=1.0,
            execution_success=0.9,
            latency=2000.0,  # Высокая latency
            error_rate=0.2
        )

        score = eval_result.calculate_score()

        # latency нормализуется: min(2000/1000, 1.0) = 1.0
        # score = 0.32 + 0.27 + 0.2 - 0.1 = 0.69
        assert abs(score - 0.69) < 0.01

    def test_to_dict(self):
        """Сериализация в словарь"""
        eval_result = EvaluationResult(
            version_id="v1",
            success_rate=0.85,
            score=0.75
        )

        data = eval_result.to_dict()

        assert data['version_id'] == "v1"
        assert data['success_rate'] == 0.85
        assert data['score'] == 0.75


class TestBenchmarkDataset:
    """Тесты для BenchmarkDataset"""

    def test_create_dataset(self):
        """Создание датасета"""
        dataset = BenchmarkDataset(
            id="ds-1",
            capability="test_cap"
        )

        assert dataset.id == "ds-1"
        assert dataset.capability == "test_cap"
        assert dataset.size == 0

    def test_add_samples(self):
        """Добавление образцов"""
        dataset = BenchmarkDataset(
            id="ds-1",
            capability="test_cap"
        )

        sample1 = OptimizationSample(id="s1", input="Input 1", success=True)
        sample2 = OptimizationSample(id="s2", input="Input 2", success=False, error="Error")

        dataset.add_sample(sample1)
        dataset.add_sample(sample2)

        assert dataset.size == 2
        assert dataset.failure_count == 1
        assert dataset.failure_rate == 0.5

    def test_get_by_type(self):
        """Получение образцов по типу"""
        dataset = BenchmarkDataset(
            id="ds-1",
            capability="test_cap"
        )

        easy = OptimizationSample(id="s1", input="Input 1", success=True)
        failure = OptimizationSample(id="s2", input="Input 2", error="Error")
        edge = OptimizationSample(id="s3", input="Input 3", success=False)

        dataset.add_sample(easy)
        dataset.add_sample(failure)
        dataset.add_sample(edge)

        easy_samples = dataset.get_by_type(ScenarioType.EASY)
        failure_samples = dataset.get_by_type(ScenarioType.FAILURE)
        edge_samples = dataset.get_by_type(ScenarioType.EDGE)

        assert len(easy_samples) == 1
        assert len(failure_samples) == 1
        assert len(edge_samples) == 1

    def test_get_type_distribution(self):
        """Получение распределения типов"""
        dataset = BenchmarkDataset(
            id="ds-1",
            capability="test_cap"
        )

        for i in range(5):
            dataset.add_sample(OptimizationSample(id=f"s{i}", input=f"Input {i}", success=True))
        for i in range(3):
            dataset.add_sample(OptimizationSample(id=f"f{i}", input=f"Input {i}", error="Error"))
        for i in range(2):
            dataset.add_sample(OptimizationSample(id=f"e{i}", input=f"Input {i}", success=False))

        distribution = dataset.get_type_distribution()

        assert distribution['easy'] == 0.5
        assert distribution['failure'] == 0.3
        assert distribution['edge'] == 0.2

    def test_to_dict(self):
        """Сериализация в словарь"""
        dataset = BenchmarkDataset(
            id="ds-1",
            capability="test_cap"
        )

        dataset.add_sample(OptimizationSample(id="s1", input="Input 1", success=True))

        data = dataset.to_dict()

        assert data['id'] == "ds-1"
        assert data['capability'] == "test_cap"
        assert data['size'] == 1
        assert len(data['samples']) == 1
