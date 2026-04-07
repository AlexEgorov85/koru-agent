"""
Тесты для OptimizationOrchestrator.

ПОКРЫТИЕ:
- Конфигурация с валидацией
- _evaluate_version через BenchmarkRunner + Evaluator
- _calculate_improvement по режимам (ACCURACY, SPEED, TOKENS, BALANCED)
- _test_and_evaluate с выбором лучшего кандидата
- Timeout enforcement
- Обработка ошибок — возврат OptimizationResult вместо None
- Rollback версий при лучшем кандидате
- Параллельный анализ
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from core.components.services.benchmarks.benchmark_models import (
    PromptVersion,
    EvaluationResult,
    OptimizationResult,
    OptimizationMode,
    BenchmarkScenario,
    BenchmarkRunResult,
    MutationType,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

from core.agent.components.optimization.orchestrator import (
    OptimizationOrchestrator,
    OrchestratorV2Config,
)


# ============================================================================
# Helper: создание mock-компонентов
# ============================================================================

def _make_event_bus():
    bus = AsyncMock(spec=UnifiedEventBus)
    bus.publish = AsyncMock()
    return bus


def _make_trace_collector(traces=None):
    collector = AsyncMock()
    collector.collect_traces = AsyncMock(return_value=traces or [])
    collector.build_dataset = AsyncMock()
    return collector


def _make_pattern_analyzer():
    analyzer = Mock()
    analyzer.analyze = Mock(return_value=[])
    analyzer.get_pattern_stats = Mock(return_value={"total_patterns": 0})
    return analyzer


def _make_prompt_analyzer():
    analyzer = Mock()
    analyzer.analyze_prompts = Mock(return_value=[])
    analyzer.analyze_responses = Mock(return_value=[])
    analyzer.get_analysis_stats = Mock(
        return_value={"total_prompt_issues": 0, "total_response_issues": 0}
    )
    return analyzer


def _make_root_cause_analyzer():
    analyzer = Mock()
    analyzer.analyze = Mock(return_value=[])
    analyzer.get_root_cause_stats = Mock(return_value={"total_root_causes": 0})
    return analyzer


def _make_example_extractor():
    extractor = Mock()
    extractor.extract_few_shot_examples = Mock(return_value=([], []))
    return extractor


def _make_benchmark_runner(results=None):
    runner = AsyncMock()
    runner.run = AsyncMock(return_value=results or [])
    return runner


def _make_evaluator(evaluation=None):
    evaluator = Mock()
    eval_result = evaluation or EvaluationResult(
        version_id="v1", success_rate=0.8, score=0.7
    )
    evaluator.evaluate = Mock(return_value=eval_result)
    return evaluator


def _make_prompt_generator(candidates=None):
    generator = AsyncMock()
    generator.generate_improvements = AsyncMock(return_value=candidates or [])
    return generator


def _make_version_manager(active_version=None):
    manager = AsyncMock()
    manager.get_active = AsyncMock(return_value=active_version)
    manager.register = AsyncMock(return_value=True)
    manager.promote = AsyncMock(return_value=True)
    manager.reject = AsyncMock(return_value=True)
    manager.rollback = AsyncMock(return_value=True)
    return manager


def _make_safety_layer(is_safe=True):
    layer = AsyncMock()
    layer.check = AsyncMock(return_value=(is_safe, []))
    return layer


def _make_baseline(capability="test_cap"):
    return PromptVersion(
        id="baseline_v1",
        parent_id=None,
        capability=capability,
        prompt="Original prompt",
        status="active",
    )


def _make_candidate(idx=1, capability="test_cap"):
    return PromptVersion(
        id=f"candidate_v{idx}",
        parent_id="baseline_v1",
        capability=capability,
        prompt=f"Improved prompt {idx}",
        status="candidate",
        mutation_type=MutationType.ADD_EXAMPLES,
    )


def _make_benchmark_results(count=5, success_count=4):
    results = []
    for i in range(count):
        results.append(
            BenchmarkRunResult(
                version_id="v1",
                scenario_id=f"s{i}",
                success=i < success_count,
                execution_time_ms=100.0,
                tokens_used=50,
            )
        )
    return results


def _build_orchestrator(
    evaluations=None,
    traces=None,
    baseline=None,
    candidates=None,
    safety_is_safe=True,
    config=None,
):
    """Универсальный билдер orchestrator с мокингом _load_scenarios_for_version"""
    event_bus = _make_event_bus()
    runner = _make_benchmark_runner(_make_benchmark_results())

    if evaluations is None:
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
        ]

    eval_idx = [0]

    def evaluate_side_effect(version_id, results):
        idx = min(eval_idx[0], len(evaluations) - 1)
        eval_idx[0] += 1
        return evaluations[idx]

    evaluator = Mock()
    evaluator.evaluate = Mock(side_effect=evaluate_side_effect)

    collector = _make_trace_collector(traces)
    vm = _make_version_manager(baseline)
    pg = _make_prompt_generator(candidates)

    orch = OptimizationOrchestrator(
        trace_collector=collector,
        pattern_analyzer=_make_pattern_analyzer(),
        prompt_analyzer=_make_prompt_analyzer(),
        root_cause_analyzer=_make_root_cause_analyzer(),
        example_extractor=_make_example_extractor(),
        benchmark_runner=runner,
        evaluator=evaluator,
        prompt_generator=pg,
        version_manager=vm,
        safety_layer=_make_safety_layer(safety_is_safe),
        event_bus=event_bus,
        config=config,
    )
    orch.executor_callback = AsyncMock()

    # Мокаем _load_scenarios_for_version чтобы возвращал сценарии
    scenarios = [Mock(spec=BenchmarkScenario)]
    orch._load_scenarios_for_version = AsyncMock(return_value=scenarios)

    return orch, runner, evaluator


# ============================================================================
# Тесты OrchestratorV2Config
# ============================================================================

class TestOrchestratorV2Config:
    """Тесты валидации конфигурации"""

    def test_default_config(self):
        config = OrchestratorV2Config()
        assert config.max_iterations == 3
        assert config.target_accuracy == 0.9
        assert config.min_improvement == 0.05
        assert config.timeout_seconds == 600

    def test_custom_config(self):
        config = OrchestratorV2Config(
            max_iterations=5,
            target_accuracy=0.95,
            min_improvement=0.1,
            timeout_seconds=300,
        )
        assert config.max_iterations == 5
        assert config.target_accuracy == 0.95

    def test_invalid_max_iterations(self):
        with pytest.raises(ValueError, match="max_iterations"):
            OrchestratorV2Config(max_iterations=0)

    def test_invalid_target_accuracy_low(self):
        with pytest.raises(ValueError, match="target_accuracy"):
            OrchestratorV2Config(target_accuracy=0.0)

    def test_invalid_target_accuracy_high(self):
        with pytest.raises(ValueError, match="target_accuracy"):
            OrchestratorV2Config(target_accuracy=1.5)

    def test_invalid_min_improvement(self):
        with pytest.raises(ValueError, match="min_improvement"):
            OrchestratorV2Config(min_improvement=-0.1)

    def test_invalid_timeout(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            OrchestratorV2Config(timeout_seconds=5)


# ============================================================================
# Тесты _calculate_improvement
# ============================================================================

class TestCalculateImprovement:
    """Тесты mode-aware расчёта улучшения"""

    def _make_orch(self):
        return _build_orchestrator()[0]

    def test_accuracy_mode(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=100)
        candidate = EvaluationResult(version_id="v2", score=0.85, latency=100)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.ACCURACY
        )
        assert abs(improvement - 0.15) < 0.001

    def test_speed_mode(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=200)
        candidate = EvaluationResult(version_id="v2", score=0.7, latency=100)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.SPEED
        )
        assert abs(improvement - 0.5) < 0.001

    def test_speed_mode_worse(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=100)
        candidate = EvaluationResult(version_id="v2", score=0.7, latency=200)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.SPEED
        )
        assert improvement < 0

    def test_tokens_mode(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=300)
        candidate = EvaluationResult(version_id="v2", score=0.7, latency=150)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.TOKENS
        )
        assert abs(improvement - 0.5) < 0.001

    def test_balanced_mode(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=200)
        candidate = EvaluationResult(version_id="v2", score=0.84, latency=100)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.BALANCED
        )
        expected = 0.7 * 0.14 + 0.3 * 0.5
        assert abs(improvement - expected) < 0.001

    def test_zero_baseline_latency(self):
        orch = self._make_orch()
        baseline = EvaluationResult(version_id="v1", score=0.7, latency=0)
        candidate = EvaluationResult(version_id="v2", score=0.7, latency=100)
        improvement = orch._calculate_improvement(
            candidate, baseline, OptimizationMode.SPEED
        )
        assert improvement == 0.0


# ============================================================================
# Тесты _evaluate_version
# ============================================================================

class TestEvaluateVersion:
    """Тесты реальной оценки через BenchmarkRunner + Evaluator"""

    @pytest.mark.asyncio
    async def test_evaluate_version_calls_benchmark(self):
        benchmark_results = _make_benchmark_results()
        evaluation = EvaluationResult(version_id="v1", success_rate=0.8, score=0.75)
        orch, runner, evaluator = _build_orchestrator(
            evaluations=[evaluation],
            traces=[Mock()],
        )
        runner.run = AsyncMock(return_value=benchmark_results)
        evaluator.evaluate = Mock(return_value=evaluation)

        version = _make_baseline()
        result = await orch._evaluate_version(version, "test_cap")

        runner.run.assert_called_once()
        evaluator.evaluate.assert_called_once()
        assert result.success_rate == 0.8
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_evaluate_version_no_scenarios(self):
        orch, _, _ = _build_orchestrator(traces=[Mock()])
        orch._load_scenarios_for_version = AsyncMock(return_value=[])

        version = _make_baseline()
        result = await orch._evaluate_version(version, "test_cap")

        assert result.success_rate == 0.0
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_version_no_callback(self):
        orch, _, _ = _build_orchestrator()
        orch.executor_callback = None

        version = _make_baseline()
        result = await orch._evaluate_version(version, "test_cap")

        assert result.success_rate == 0.0


# ============================================================================
# Тесты _test_and_evaluate
# ============================================================================

class TestTestAndEvaluate:
    """Тесты тестирования и оценки кандидатов"""

    @pytest.mark.asyncio
    async def test_no_executor_callback(self):
        orch, _, _ = _build_orchestrator()
        orch.executor_callback = None
        baseline = _make_baseline()

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=[_make_candidate()],
            mode=OptimizationMode.ACCURACY,
        )

        assert result.status == "failed"
        assert "Executor callback" in result.error

    @pytest.mark.asyncio
    async def test_finds_best_candidate(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.75, score=0.65, latency=180),
            EvaluationResult(version_id="candidate_v2", success_rate=0.9, score=0.85, latency=100),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations, baseline=_make_baseline())

        baseline = _make_baseline()
        candidates = [_make_candidate(1), _make_candidate(2)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.to_version == "candidate_v2"
        assert orch.version_manager.promote.call_count == 1
        orch.version_manager.promote.assert_called_with("candidate_v2", "test_cap")

    @pytest.mark.asyncio
    async def test_no_improvement(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.9, score=0.85, latency=100),
            EvaluationResult(version_id="candidate_v1", success_rate=0.85, score=0.8, latency=120),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations)

        baseline = _make_baseline()
        candidates = [_make_candidate(1)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.to_version == baseline.id
        assert result.status == "completed"
        assert not result.target_achieved

    @pytest.mark.asyncio
    async def test_safety_check_rejects_unsafe(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.9, score=0.85, latency=100),
        ]
        orch, _, _ = _build_orchestrator(
            evaluations=evaluations, safety_is_safe=False
        )

        baseline = _make_baseline()
        candidates = [_make_candidate(1)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.to_version == baseline.id
        orch.version_manager.reject.assert_called()

    @pytest.mark.asyncio
    async def test_rollback_before_promote(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.9, score=0.85, latency=100),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations)

        previous_active = PromptVersion(
            id="previous_active",
            parent_id="baseline_v1",
            capability="test_cap",
            prompt="Previous",
            status="active",
        )
        orch.version_manager.get_active = AsyncMock(return_value=previous_active)

        baseline = _make_baseline()
        candidates = [_make_candidate(1)]

        await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        orch.version_manager.rollback.assert_called_once_with("test_cap", "baseline_v1")
        orch.version_manager.promote.assert_called_once_with("candidate_v1", "test_cap")

    @pytest.mark.asyncio
    async def test_target_achieved(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.95, score=0.9, latency=80),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations)

        baseline = _make_baseline()
        candidates = [_make_candidate(1)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.target_achieved is True

    @pytest.mark.asyncio
    async def test_iterations_count(self):
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.72, score=0.62, latency=190),
            EvaluationResult(version_id="candidate_v2", success_rate=0.73, score=0.63, latency=185),
            EvaluationResult(version_id="candidate_v3", success_rate=0.74, score=0.64, latency=180),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations)

        baseline = _make_baseline()
        candidates = [_make_candidate(1), _make_candidate(2), _make_candidate(3)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.iterations == 3

    @pytest.mark.asyncio
    async def test_respects_max_iterations(self):
        config = OrchestratorV2Config(max_iterations=2)
        evaluations = [
            EvaluationResult(version_id="baseline_v1", success_rate=0.7, score=0.6, latency=200),
            EvaluationResult(version_id="candidate_v1", success_rate=0.75, score=0.65, latency=180),
            EvaluationResult(version_id="candidate_v2", success_rate=0.8, score=0.7, latency=150),
            EvaluationResult(version_id="candidate_v3", success_rate=0.85, score=0.75, latency=120),
        ]
        orch, _, _ = _build_orchestrator(evaluations=evaluations, config=config)

        baseline = _make_baseline()
        candidates = [_make_candidate(1), _make_candidate(2), _make_candidate(3)]

        result = await orch._test_and_evaluate(
            capability="test_cap",
            baseline=baseline,
            candidates=candidates,
            mode=OptimizationMode.ACCURACY,
        )

        assert result.iterations == 2


# ============================================================================
# Тесты optimize() — обработка ошибок и timeout
# ============================================================================

class TestOptimize:
    """Тесты основного метода optimize"""

    @pytest.mark.asyncio
    async def test_no_traces_returns_result(self):
        orch, _, _ = _build_orchestrator(traces=[])

        result = await orch.optimize("test_cap")

        assert result is not None
        assert result.status == "no_traces"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_no_baseline_returns_result(self):
        orch, _, _ = _build_orchestrator(traces=[Mock()], baseline=None)

        result = await orch.optimize("test_cap")

        assert result is not None
        assert result.status == "no_baseline"

    @pytest.mark.asyncio
    async def test_no_candidates_returns_result(self):
        orch, _, _ = _build_orchestrator(
            traces=[Mock()],
            baseline=_make_baseline(),
            candidates=[],
        )

        result = await orch.optimize("test_cap")

        assert result is not None
        assert result.status == "no_candidates"

    @pytest.mark.asyncio
    async def test_exception_returns_failed_result(self):
        orch, _, _ = _build_orchestrator(traces=[Mock()])
        orch.trace_collector.collect_traces = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        result = await orch.optimize("test_cap")

        assert result is not None
        assert result.status == "failed"
        assert "DB connection lost" in result.error

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_result(self):
        orch, _, _ = _build_orchestrator(
            traces=[Mock()],
            config=OrchestratorV2Config(timeout_seconds=10),
        )

        async def slow_collect(cap):
            await asyncio.sleep(30)
            return [Mock()]

        orch.trace_collector.collect_traces = slow_collect

        result = await orch.optimize("test_cap")

        assert result is not None
        assert result.status == "timeout"
        assert "таймаут" in result.error

    @pytest.mark.asyncio
    async def test_publishes_events(self):
        orch, _, _ = _build_orchestrator(
            traces=[Mock()],
            baseline=_make_baseline(),
            candidates=[],
        )

        await orch.optimize("test_cap")

        assert orch.event_bus.publish.call_count > 0


# ============================================================================
# Тесты OptimizationResult
# ============================================================================

class TestOptimizationResult:
    """Тесты модели OptimizationResult"""

    def test_default_status(self):
        result = OptimizationResult(
            capability="test",
            from_version="v1",
            to_version="v1",
            mode=OptimizationMode.ACCURACY,
        )
        assert result.status == "completed"

    def test_failed_status_with_error(self):
        result = OptimizationResult(
            capability="test",
            from_version="v1",
            to_version="v1",
            mode=OptimizationMode.ACCURACY,
            status="failed",
            error="Something went wrong",
        )
        assert result.status == "failed"
        assert result.error == "Something went wrong"

    def test_to_dict_includes_status_and_error(self):
        result = OptimizationResult(
            capability="test",
            from_version="v1",
            to_version="v2",
            mode=OptimizationMode.SPEED,
            status="completed",
            error=None,
        )
        data = result.to_dict()
        assert data["status"] == "completed"
        assert data["error"] is None
        assert data["mode"] == "speed"

    def test_calculate_improvements(self):
        result = OptimizationResult(
            capability="test",
            from_version="v1",
            to_version="v2",
            mode=OptimizationMode.ACCURACY,
            initial_metrics={"success_rate": 0.7, "score": 0.6},
            final_metrics={"success_rate": 0.85, "score": 0.75},
        )
        result.calculate_improvements()

        assert abs(result.improvements["success_rate"] - 21.43) < 0.1
        assert abs(result.improvements["score"] - 25.0) < 0.1


# ============================================================================
# Тесты get_optimization_report
# ============================================================================

class TestGetOptimizationReport:

    def _make_orch(self):
        return _build_orchestrator()[0]

    def test_report_for_none(self):
        orch = self._make_orch()
        report = orch.get_optimization_report(None)
        assert report["status"] == "failed"

    def test_report_for_result(self):
        orch = self._make_orch()
        result = OptimizationResult(
            capability="test",
            from_version="v1",
            to_version="v2",
            mode=OptimizationMode.ACCURACY,
            status="completed",
            iterations=2,
            target_achieved=True,
            initial_metrics={"score": 0.6},
            final_metrics={"score": 0.8},
        )
        report = orch.get_optimization_report(result)

        assert report["status"] == "completed"
        assert report["capability"] == "test"
        assert report["iterations"] == 2
        assert report["target_achieved"] is True
        assert report["error"] is None
