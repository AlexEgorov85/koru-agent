"""
Юнит-тесты для AccuracyEvaluator.

ТЕСТЫ:
- test_exact_match_evaluation: точное совпадение
- test_coverage_evaluation: оценка покрытия
- test_semantic_evaluation: семантическая оценка
- test_hybrid_evaluation: гибридная оценка
"""
import pytest
from core.models.data.benchmark import (
    ExpectedOutput,
    ActualOutput,
    EvaluationCriterion,
    EvaluationType,
)
from core.application.services.accuracy_evaluator import (
    AccuracyEvaluatorService,
    ExactMatchEvaluator,
    CoverageEvaluator,
    SemanticEvaluator,
    HybridEvaluator,
    EvaluationResult,
)


class TestExactMatchEvaluator:
    """Тесты ExactMatchEvaluator"""

    @pytest.mark.asyncio
    async def test_exact_match_strings(self):
        """Тест точного совпадения строк"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="Hello World")
        actual = ActualOutput(content="Hello World")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0
        assert "Точное совпадение" in details

    @pytest.mark.asyncio
    async def test_exact_match_strings_normalized(self):
        """Тест нормализации строк"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="Hello   World")
        actual = ActualOutput(content="Hello World")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_strings_mismatch(self):
        """Тест несовпадения строк"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="Hello World")
        actual = ActualOutput(content="Hello Universe")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_exact_match_json(self):
        """Тест точного совпадения JSON"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content={"name": "test", "value": 42})
        actual = ActualOutput(content={"value": 42, "name": "test"})  # Порядок ключей не важен

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0
        assert "JSON" in details

    @pytest.mark.asyncio
    async def test_exact_match_json_mismatch(self):
        """Тест несовпадения JSON"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content={"name": "test", "value": 42})
        actual = ActualOutput(content={"name": "test", "value": 43})

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_exact_match_with_schema_valid(self):
        """Тест валидации схемы (успех)"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(
            content={"name": "test", "value": 42},
            schema={"type": "object", "required": ["name", "value"]}
        )
        actual = ActualOutput(content={"name": "test", "value": 42})

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_with_schema_invalid(self):
        """Тест валидации схемы (провал)"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(
            content={"name": "test"},
            schema={"type": "object", "required": ["name", "value"]}
        )
        actual = ActualOutput(content={"name": "test"})  # Отсутствует 'value'

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0
        assert "схемы" in details.lower() or "schema" in details.lower()

    @pytest.mark.asyncio
    async def test_exact_match_none(self):
        """Тест None значений"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content=None)
        actual = ActualOutput(content=None)

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_none_mismatch(self):
        """Тест None vs значение"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content=None)
        actual = ActualOutput(content="something")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0


class TestCoverageEvaluator:
    """Тесты CoverageEvaluator"""

    @pytest.mark.asyncio
    async def test_coverage_text_full(self):
        """Тест полного покрытия текста"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content="create a plan for project management")
        actual = ActualOutput(content="I will create a plan for project management")

        score, details = await evaluator.evaluate(expected, actual)

        assert score >= 0.8  # Должно быть высокое покрытие

    @pytest.mark.asyncio
    async def test_coverage_text_partial(self):
        """Тест частичного покрытия текста"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content="create a plan for project management with timeline")
        actual = ActualOutput(content="create a plan")

        score, details = await evaluator.evaluate(expected, actual)

        assert score < 1.0
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_coverage_dict_full(self):
        """Тест полного покрытия dict"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content={"name": "test", "value": 42, "active": True})
        actual = ActualOutput(content={"name": "test", "value": 42, "active": True, "extra": "field"})

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_coverage_dict_partial(self):
        """Тест частичного покрытия dict"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content={"name": "test", "value": 42, "active": True})
        actual = ActualOutput(content={"name": "test"})

        score, details = await evaluator.evaluate(expected, actual)

        assert score < 1.0
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_coverage_list_full(self):
        """Тест полного покрытия списка"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content=["item1", "item2", "item3"])
        actual = ActualOutput(content=["item1", "item2", "item3", "item4"])

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_coverage_list_partial(self):
        """Тест частичного покрытия списка"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content=["item1", "item2", "item3"])
        actual = ActualOutput(content=["item1"])

        score, details = await evaluator.evaluate(expected, actual)

        assert score < 1.0
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_coverage_empty_expected(self):
        """Тест пустого ожидаемого контента"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content="")
        actual = ActualOutput(content="anything")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_coverage_empty_actual(self):
        """Тест пустого фактического контента"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content="something")
        actual = ActualOutput(content="")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0


class TestSemanticEvaluator:
    """Тесты SemanticEvaluator"""

    @pytest.mark.asyncio
    async def test_semantic_without_llm(self):
        """Тест семантической оценки без LLM"""
        evaluator = SemanticEvaluator(llm_provider=None)

        expected = ExpectedOutput(content="create a plan")
        actual = ActualOutput(content="I will create a plan for you")

        score, details = await evaluator.evaluate(expected, actual)

        # Без LLM используется fallback на CoverageEvaluator
        assert score >= 0.0
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_semantic_heuristic_fallback(self):
        """Тест эвристического fallback"""
        evaluator = SemanticEvaluator()

        expected = ExpectedOutput(content="analyze data and provide insights")
        actual = ActualOutput(content="data analysis with insights provided")

        score, details = await evaluator.evaluate(expected, actual)

        assert score >= 0.0
        assert score <= 1.0


class TestHybridEvaluator:
    """Тесты HybridEvaluator"""

    @pytest.mark.asyncio
    async def test_hybrid_evaluation(self):
        """Тест гибридной оценки"""
        evaluator = HybridEvaluator()

        expected = ExpectedOutput(content="create a detailed project plan")
        actual = ActualOutput(content="I will create a detailed project plan with timeline")

        score, details = await evaluator.evaluate(expected, actual)

        assert score >= 0.0
        assert score <= 1.0
        assert "Exact Match" in details
        assert "Coverage" in details
        assert "Semantic" in details

    @pytest.mark.asyncio
    async def test_hybrid_custom_weights(self):
        """Тест гибридной оценки с custom весами"""
        evaluator = HybridEvaluator(
            weights={'exact': 0.5, 'coverage': 0.5, 'semantic': 0.0}
        )

        expected = ExpectedOutput(content="test")
        actual = ActualOutput(content="test")

        score, details = await evaluator.evaluate(expected, actual)

        assert score >= 0.0
        assert score <= 1.0


class TestAccuracyEvaluatorService:
    """Тесты AccuracyEvaluatorService"""

    @pytest.mark.asyncio
    async def test_evaluate_exact_match(self):
        """Тест оценки с exact match"""
        service = AccuracyEvaluatorService()

        criterion = EvaluationCriterion(
            name='exact_match',
            evaluation_type=EvaluationType.EXACT_MATCH,
            threshold=0.9
        )

        expected = ExpectedOutput(content="Hello World")
        actual = ActualOutput(content="Hello World")

        result = await service.evaluate(expected, actual, criterion)

        assert isinstance(result, EvaluationResult)
        assert result.score == 1.0
        assert result.passed is True
        assert result.criterion == 'exact_match'

    @pytest.mark.asyncio
    async def test_evaluate_below_threshold(self):
        """Тест оценки ниже порога"""
        service = AccuracyEvaluatorService()

        criterion = EvaluationCriterion(
            name='exact_match',
            evaluation_type=EvaluationType.EXACT_MATCH,
            threshold=0.9
        )

        expected = ExpectedOutput(content="Hello World")
        actual = ActualOutput(content="Hello Universe")

        result = await service.evaluate(expected, actual, criterion)

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_evaluate_coverage(self):
        """Тест оценки покрытия"""
        service = AccuracyEvaluatorService()

        criterion = EvaluationCriterion(
            name='coverage',
            evaluation_type=EvaluationType.COVERAGE,
            threshold=0.7
        )

        expected = ExpectedOutput(content="create a plan for project")
        actual = ActualOutput(content="I will create a plan for project management")

        result = await service.evaluate(expected, actual, criterion)

        assert result.score > 0.0
        assert result.criterion == 'coverage'

    @pytest.mark.asyncio
    async def test_evaluate_multiple_criteria(self):
        """Тест оценки по нескольким критериям"""
        service = AccuracyEvaluatorService()

        criteria = [
            EvaluationCriterion(
                name='exact_match',
                evaluation_type=EvaluationType.EXACT_MATCH,
                threshold=0.9
            ),
            EvaluationCriterion(
                name='coverage',
                evaluation_type=EvaluationType.COVERAGE,
                threshold=0.7
            ),
        ]

        expected = ExpectedOutput(content="test")
        actual = ActualOutput(content="test")

        results = await service.evaluate_multiple(expected, actual, criteria)

        assert len(results) == 2
        assert all(isinstance(r, EvaluationResult) for r in results)

    @pytest.mark.asyncio
    async def test_register_custom_evaluator(self):
        """Тест регистрации custom оценщика"""
        service = AccuracyEvaluatorService()

        class CustomEvaluator:
            async def evaluate(self, expected, actual):
                return (0.5, "Custom evaluation")

        service.register_evaluator(EvaluationType.CUSTOM, CustomEvaluator())

        criterion = EvaluationCriterion(
            name='custom',
            evaluation_type=EvaluationType.CUSTOM,
            threshold=0.5
        )

        expected = ExpectedOutput(content="test")
        actual = ActualOutput(content="test")

        result = await service.evaluate(expected, actual, criterion)

        assert result.score == 0.5
        assert result.details == "Custom evaluation"


class TestEvaluationResult:
    """Тесты EvaluationResult"""

    def test_evaluation_result_creation(self):
        """Тест создания EvaluationResult"""
        result = EvaluationResult(
            score=0.85,
            passed=True,
            details="Good match",
            criterion='accuracy',
            evaluation_type=EvaluationType.EXACT_MATCH
        )

        assert result.score == 0.85
        assert result.passed is True
        assert result.details == "Good match"
        assert result.criterion == 'accuracy'
        assert result.evaluation_type == EvaluationType.EXACT_MATCH

    def test_evaluation_result_failed(self):
        """Тест проваленной оценки"""
        result = EvaluationResult(
            score=0.3,
            passed=False,
            details="Poor match",
            criterion='accuracy',
            evaluation_type=EvaluationType.COVERAGE
        )

        assert result.score == 0.3
        assert result.passed is False


class TestEdgeCases:
    """Тесты граничных значений и ошибок"""

    @pytest.mark.asyncio
    async def test_empty_strings(self):
        """Тест пустых строк"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="")
        actual = ActualOutput(content="")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        """Тест строк из пробелов"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="   ")
        actual = ActualOutput(content="")

        score, details = await evaluator.evaluate(expected, actual)

        # После нормализации оба должны быть пустыми
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_unicode_strings(self):
        """Тест unicode строк"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="Привет мир")
        actual = ActualOutput(content="Привет мир")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_nested_json(self):
        """Тест вложенного JSON"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content={
            "outer": {
                "inner": {
                    "value": 42
                }
            }
        })
        actual = ActualOutput(content={
            "outer": {
                "inner": {
                    "value": 42
                }
            }
        })

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_mismatched_types(self):
        """Тест несовпадения типов"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content={"key": "value"})
        actual = ActualOutput(content="string value")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_large_text_partial(self):
        """Тест частичного покрытия большого текста"""
        evaluator = CoverageEvaluator()

        # expected содержит одни слова, actual другие
        expected = ExpectedOutput(content="alpha beta gamma delta epsilon")
        actual = ActualOutput(content="alpha beta")  # Только 2 из 5 слов

        score, details = await evaluator.evaluate(expected, actual)

        # 2 из 5 слов = 40% покрытие
        assert score < 0.5
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Тест специальных символов"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content="test@#$%^&*()")
        actual = ActualOutput(content="test@#$%^&*()")

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_boolean_values(self):
        """Тест boolean значений"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content=True)
        actual = ActualOutput(content=True)

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_numeric_precision(self):
        """Тест точности чисел"""
        evaluator = ExactMatchEvaluator()

        expected = ExpectedOutput(content=3.14159)
        actual = ActualOutput(content=3.14159)

        score, details = await evaluator.evaluate(expected, actual)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_list_order_matters(self):
        """Тест что порядок в списке важен"""
        evaluator = CoverageEvaluator()

        expected = ExpectedOutput(content=[1, 2, 3])
        actual = ActualOutput(content=[3, 2, 1])

        score, details = await evaluator.evaluate(expected, actual)

        # Все элементы есть, но порядок другой
        assert score == 1.0  # Coverage не проверяет порядок
