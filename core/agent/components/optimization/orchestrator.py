"""
OptimizationOrchestrator — оркестрация с полным анализом traces.

ОТВЕТСТВЕННОСТЬ:
- Оркестрация всех компонентов оптимизации
- Анализ execution traces
- Поиск корневых причин
- Умная генерация улучшений
- Реальная оценка через BenchmarkRunner + Evaluator
- Timeout enforcement
- Mode-aware оценка (ACCURACY, SPEED, TOKENS, BALANCED)

ПИПЛАЙН:
1. traces = trace_collector.collect_traces()
2. patterns, prompt_issues, response_issues = asyncio.gather(...)
3. root_causes = root_cause_analyzer.analyze(...)
4. examples, error_examples = example_extractor.extract_few_shot_examples(...)
5. candidates = prompt_generator.generate_improvements(...)
6. test + evaluate + safety check → promote
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable

from core.components.benchmarks.benchmark_models import (
    PromptVersion,
    EvaluationResult,
    OptimizationResult,
    OptimizationMode,
    BenchmarkScenario,
    BenchmarkRunResult,
    ExpectedOutput,
    EvaluationCriterion,
    EvaluationType,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


from .trace_collector import TraceCollector
from .pattern_analyzer import PatternAnalyzer
from .prompt_analyzer import PromptResponseAnalyzer
from .root_cause_analyzer import RootCauseAnalyzer
from .example_extractor import ExampleExtractor
from .evaluator import Evaluator
from .prompt_generator import PromptGenerator
from .version_manager import VersionManager
from .safety_layer import SafetyLayer
from .scenario_builder import ScenarioBuilder

from core.components.benchmarks.benchmark_runner import BenchmarkRunner


class OrchestratorV2Config:
    """Конфигурация OptimizationOrchestrator v2 с валидацией"""

    def __init__(
        self,
        max_iterations: int = 3,
        target_accuracy: float = 0.9,
        min_improvement: float = 0.05,
        timeout_seconds: int = 600,
        max_examples: int = 5,
        max_error_examples: int = 3,
        benchmark_size: int = 2,
        baseline_results: Optional[Dict[str, Any]] = None,
    ):
        if max_iterations < 1:
            raise ValueError(f"max_iterations должен быть >= 1, получено {max_iterations}")
        if not (0.0 < target_accuracy <= 1.0):
            raise ValueError(f"target_accuracy должен быть в (0.0, 1.0], получено {target_accuracy}")
        if not (0.0 <= min_improvement < 1.0):
            raise ValueError(f"min_improvement должен быть в [0.0, 1.0), получено {min_improvement}")
        if timeout_seconds < 10:
            raise ValueError(f"timeout_seconds должен быть >= 10, получено {timeout_seconds}")
        if max_examples < 1:
            raise ValueError(f"max_examples должен быть >= 1, получено {max_examples}")
        if benchmark_size < 1:
            raise ValueError(f"benchmark_size должен быть >= 1, получено {benchmark_size}")

        self.max_iterations = max_iterations
        self.target_accuracy = target_accuracy
        self.min_improvement = min_improvement
        self.timeout_seconds = timeout_seconds
        self.max_examples = max_examples
        self.max_error_examples = max_error_examples
        self.benchmark_size = benchmark_size
        self.baseline_results = baseline_results


class OptimizationOrchestrator:
    """
    Оркестратор цикла оптимизации промптов.

    RESPONSIBILITIES:
    - Координация компонентов оптимизации
    - Анализ execution traces
    - Поиск корневых причин проблем
    - Генерация целевых улучшений
    - Реальная оценка через BenchmarkRunner + Evaluator
    - Timeout enforcement
    - Mode-aware оценка

    USAGE:
    ```python
    orchestrator = OptimizationOrchestrator(
        trace_collector, pattern_analyzer, prompt_analyzer,
        root_cause_analyzer, example_extractor, ...
    )
    result = await orchestrator.optimize(capability)
    ```
    """

    def __init__(
        self,
        trace_collector: TraceCollector,
        pattern_analyzer: PatternAnalyzer,
        prompt_analyzer: PromptResponseAnalyzer,
        root_cause_analyzer: RootCauseAnalyzer,
        example_extractor: ExampleExtractor,
        benchmark_runner: BenchmarkRunner,
        evaluator: Evaluator,
        prompt_generator: PromptGenerator,
        version_manager: VersionManager,
        safety_layer: SafetyLayer,
        event_bus: UnifiedEventBus,
        config: Optional[OrchestratorV2Config] = None
    ):
        """
        Инициализация OptimizationOrchestrator v2.

        ARGS:
        - trace_collector: сборщик traces
        - pattern_analyzer: анализатор паттернов
        - prompt_analyzer: анализатор промптов/ответов
        - root_cause_analyzer: анализатор корневых причин
        - example_extractor: извлекатель примеров
        - benchmark_runner: раннер бенчмарков
        - evaluator: оценщик качества
        - prompt_generator: генератор промптов
        - version_manager: менеджер версий
        - safety_layer: слой безопасности
        - event_bus: шина событий
        - config: конфигурация
        """
        self.trace_collector = trace_collector
        self.pattern_analyzer = pattern_analyzer
        self.prompt_analyzer = prompt_analyzer
        self.root_cause_analyzer = root_cause_analyzer
        self.example_extractor = example_extractor
        self.benchmark_runner = benchmark_runner
        self.evaluator = evaluator
        self.prompt_generator = prompt_generator
        self.version_manager = version_manager
        self.safety_layer = safety_layer
        self.event_bus = event_bus
        self.config = config or OrchestratorV2Config()

        # Callback для выполнения промптов
        self.executor_callback: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None

    def set_executor_callback(
        self,
        callback: Callable[[str, str], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Установка callback для выполнения промптов"""
        self.executor_callback = callback

    async def optimize(
        self,
        capability: str,
        mode: OptimizationMode = OptimizationMode.ACCURACY
    ) -> OptimizationResult:
        """
        Запуск цикла оптимизации.

        ЭТАПЫ:
        1. Сбор traces
        2. Параллельный анализ паттернов, промптов, ответов
        3. Поиск корневых причин
        4. Извлечение примеров
        5. Генерация улучшений
        6. Тестирование и оценка кандидатов
        7. Продвижение лучшей версии

        ARGS:
        - capability: название способности
        - mode: режим оптимизации (ACCURACY, SPEED, TOKENS, BALANCED)

        RETURNS:
        - OptimizationResult: результат оптимизации (никогда None)
        """
        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "mode": mode.value,
                "phase": "started",
                "timeout_seconds": self.config.timeout_seconds,
            },
        )

        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(
                self._run_optimization_pipeline(capability, mode),
                timeout=self.config.timeout_seconds,
            )
            return result

        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start_time).total_seconds()
            await self._publish_event(
                EventType.ERROR_OCCURRED,
                {
                    "capability": capability,
                    "error": f"Optimization pipeline timed out after {elapsed:.1f}s (limit: {self.config.timeout_seconds}s)",
                    "phase": "timeout",
                },
            )
            return OptimizationResult(
                capability=capability,
                from_version="unknown",
                to_version="unknown",
                mode=mode,
                status="timeout",
                error=f"Оптимизация превысила таймаут {self.config.timeout_seconds}с",
            )

        except Exception as e:
            await self._publish_event(
                EventType.ERROR_OCCURRED,
                {
                    "capability": capability,
                    "error": str(e),
                    "phase": "failed",
                },
            )
            return OptimizationResult(
                capability=capability,
                from_version="unknown",
                to_version="unknown",
                mode=mode,
                status="failed",
                error=str(e),
            )

    async def _run_optimization_pipeline(
        self,
        capability: str,
        mode: OptimizationMode,
    ) -> OptimizationResult:
        """
        Внутренний пайплайн оптимизации.

        ARGS:
        - capability: название способности
        - mode: режим оптимизации

        RETURNS:
        - OptimizationResult: результат
        """
        start_time = datetime.now()

        # ЭТАП 1: Сбор traces
        traces = await self.trace_collector.collect_traces(capability)

        if not traces:
            await self._publish_event(
                EventType.OPTIMIZATION_CYCLE_COMPLETED,
                {"capability": capability, "phase": "no_traces"},
            )
            return OptimizationResult(
                capability=capability,
                from_version="unknown",
                to_version="unknown",
                mode=mode,
                status="no_traces",
                error=f"Не найдено traces для {capability}",
            )

        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "phase": "traces_collected",
                "traces_count": len(traces),
            },
        )

        # ЭТАП 2-4: Параллельный анализ
        patterns_task = asyncio.to_thread(self.pattern_analyzer.analyze, traces)
        prompt_issues_task = asyncio.to_thread(self.prompt_analyzer.analyze_prompts, traces)
        response_issues_task = asyncio.to_thread(self.prompt_analyzer.analyze_responses, traces)

        patterns, prompt_issues, response_issues = await asyncio.gather(
            patterns_task,
            prompt_issues_task,
            response_issues_task,
        )

        pattern_stats = self.pattern_analyzer.get_pattern_stats(patterns)
        analysis_stats = self.prompt_analyzer.get_analysis_stats(prompt_issues, response_issues)

        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "phase": "analysis_completed",
                "patterns": pattern_stats,
                "analysis_stats": analysis_stats,
            },
        )

        # ЭТАП 5: Поиск корневых причин
        root_causes = self.root_cause_analyzer.analyze(
            patterns, prompt_issues, response_issues
        )
        cause_stats = self.root_cause_analyzer.get_root_cause_stats(root_causes)

        # ЭТАП 6: Извлечение примеров
        good_examples, error_examples = self.example_extractor.extract_few_shot_examples(
            traces,
            capability,
            num_good=self.config.max_examples,
            num_bad=self.config.max_error_examples,
        )

        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "phase": "examples_extracted",
                "good_examples": len(good_examples),
                "error_examples": len(error_examples),
                "root_causes": cause_stats,
            },
        )

        # DEBUG: Показать root causes
        print(f"\n  🔍 [Debug] Root causes ({len(root_causes)}):")
        for i, rc in enumerate(root_causes):
            print(f"    {i+1}. cause='{rc.cause}' fix='{rc.fix}' caps={rc.affected_capabilities} related={rc.related_issues}")

        # ЭТАП 7: Получение baseline и генерация улучшений
        baseline = await self.version_manager.get_active(capability)

        if not baseline:
            return OptimizationResult(
                capability=capability,
                from_version="unknown",
                to_version="unknown",
                mode=mode,
                status="no_baseline",
                error=f"Baseline версия не найдена для {capability}",
            )

        candidates = await self.prompt_generator.generate_improvements(
            original_prompt=baseline,
            root_causes=root_causes,
            good_examples=good_examples,
            error_examples=error_examples,
        )

        if not candidates:
            return OptimizationResult(
                capability=capability,
                from_version=baseline.id,
                to_version=baseline.id,
                mode=mode,
                status="no_candidates",
                error="Кандидаты не сгенерированы",
            )

        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "phase": "candidates_generated",
                "candidates_count": len(candidates),
            },
        )

        # ЭТАП 8: Тестирование и оценка
        result = await self._test_and_evaluate(
            capability=capability,
            baseline=baseline,
            candidates=candidates,
            mode=mode,
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        await self._publish_event(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            {
                "capability": capability,
                "phase": "completed",
                "elapsed_seconds": elapsed,
                "status": result.status,
                "target_achieved": result.target_achieved,
            },
        )

        return result

    async def _test_and_evaluate(
        self,
        capability: str,
        baseline: PromptVersion,
        candidates: List[PromptVersion],
        mode: OptimizationMode,
    ) -> OptimizationResult:
        """
        Тестирование и оценка кандидатов с учётом режима оптимизации.

        Все кандидаты тестируются, лучший выбирается по mode-specific метрике.
        Продвижение происходит только один раз — для лучшего кандидата.

        ARGS:
        - capability: название способности
        - baseline: baseline версия
        - candidates: кандидаты
        - mode: режим оптимизации

        RETURNS:
        - OptimizationResult: результат
        """
        if not self.executor_callback:
            return OptimizationResult(
                capability=capability,
                from_version=baseline.id,
                to_version=baseline.id,
                mode=mode,
                status="failed",
                error="Executor callback не установлен",
            )

        # Оценка baseline
        print(f"\n  📊 [Evaluate] Оценка baseline: {baseline.id}")
        baseline_eval = await self._evaluate_version_with_baseline(
            baseline, capability, self.config.baseline_results
        )
        print(f"  📊 [Evaluate] Baseline eval: success_rate={baseline_eval.success_rate}, score={baseline_eval.score}")

        # Инициализация результата
        result = OptimizationResult(
            capability=capability,
            from_version=baseline.id,
            to_version=baseline.id,
            mode=mode,
            iterations=0,
            initial_metrics={
                "success_rate": baseline_eval.success_rate,
                "score": baseline_eval.score,
                "latency": baseline_eval.latency,
            },
        )

        # Тестируем всех кандидатов, запоминаем лучшего
        best_candidate: Optional[PromptVersion] = None
        best_eval: Optional[EvaluationResult] = None
        best_improvement = 0.0

        evaluated_candidates: List[tuple] = []

        for iteration, candidate in enumerate(candidates[: self.config.max_iterations]):
            result.iterations = iteration + 1

            # Регистрация кандидата
            await self.version_manager.register(candidate)

            # Оценка кандидата
            print(f"  📊 [Evaluate] Оценка кандидата: {candidate.id}")
            candidate_eval = await self._evaluate_version(candidate, capability)
            print(f"  📊 [Evaluate] Candidate eval: success_rate={candidate_eval.success_rate}, score={candidate_eval.score}")

            # Расчёт улучшения по mode-specific метрике
            improvement = self._calculate_improvement(
                candidate_eval, baseline_eval, mode
            )
            print(f"  📊 [Evaluate] Improvement: {improvement:.4f} (min: {self.config.min_improvement})")

            evaluated_candidates.append((candidate, candidate_eval, improvement))

            print(f"\n  🔍 [Evaluate] Кандидат: {candidate.id}")
            print(f"     improvement: {improvement:.4f} (min: {self.config.min_improvement})")
            
            if improvement >= self.config.min_improvement:
                # Проверка безопасности
                is_safe, checks = await self.safety_layer.check(
                    candidate_eval, baseline_eval
                )
                print(f"     is_safe: {is_safe}, checks: {[c.check_type.value for c in checks]}")

                if is_safe and improvement > best_improvement:
                    best_candidate = candidate
                    best_eval = candidate_eval
                    best_improvement = improvement
                    print(f"     ★ НОВЫЙ ЛУЧШИЙ! best_improvement={best_improvement:.4f}")

                    await self._publish_event(
                        EventType.OPTIMIZATION_CYCLE_COMPLETED,
                        {
                            "capability": capability,
                            "phase": "candidate_evaluated",
                            "iteration": iteration + 1,
                            "improvement": improvement,
                            "score": candidate_eval.score,
                            "is_best": True,
                        },
                    )
                else:
                    reason = "Safety check failed" if not is_safe else "Not better than current best"
                    print(f"     → Rejected: {reason}")
                    await self.version_manager.reject(
                        candidate.id,
                        capability,
                        reason,
                    )
            else:
                print(f"     → Rejected: Insufficient improvement")
                await self.version_manager.reject(
                    candidate.id, capability, "Insufficient improvement"
                )

        # Продвижение лучшего кандидата (один раз)
        if best_candidate and best_eval and best_improvement > 0:
            print(f"\n  🎯 ПРОМОУЖН: Лучший кандидент найден!")
            print(f"     best_candidate: {best_candidate.id}")
            print(f"     best_eval.score: {best_eval.score}")
            print(f"     best_improvement: {best_improvement:.4f}")
            print(f"     baseline.id: {baseline.id}")
            print(f"\n  🎯 ПРОМОУЖН: Лучший кандидент найден!")
            print(f"     best_candidate: {best_candidate.id}")
            print(f"     best_eval.score: {best_eval.score}")
            print(f"     best_improvement: {best_improvement:.4f}")
            print(f"     min_improvement: {self.config.min_improvement}")
            print(f"     baseline.id: {baseline.id}")

            # Откат предыдущей active версии (если была продвинута ранее в цикле)
            current_active = await self.version_manager.get_active(capability)
            print(f"     current_active: {current_active.id if current_active else None}")
            
            if current_active and current_active.id != baseline.id:
                await self.version_manager.rollback(capability, baseline.id)
                print(f"     → Rollback выполнен")

            # Продвижение лучшего
            await self.version_manager.promote(best_candidate.id, capability)
            print(f"     → Promote выполнен для {best_candidate.id}")

            result.to_version = best_candidate.id
            result.final_metrics = {
                "success_rate": best_eval.success_rate,
                "score": best_eval.score,
                "latency": best_eval.latency,
            }
            result.target_achieved = best_eval.success_rate >= self.config.target_accuracy
            print(f"     → to_version: {result.to_version}")
        else:
            print(f"\n  ⚠️ ПРОМОУЖН: Лучший кандидент НЕ найден")
            print(f"     best_candidate: {best_candidate}")
            print(f"     best_eval: {best_eval}")
            print(f"     best_improvement: {best_improvement:.4f}")
            # Улучшений не найдено — остаёмся на baseline
            result.final_metrics = {
                "success_rate": baseline_eval.success_rate,
                "score": baseline_eval.score,
                "latency": baseline_eval.latency,
            }

        result.calculate_improvements()

        return result

    def _calculate_improvement(
        self,
        candidate_eval: EvaluationResult,
        baseline_eval: EvaluationResult,
        mode: OptimizationMode,
    ) -> float:
        """
        Расчёт улучшения с учётом режима оптимизации.

        ARGS:
        - candidate_eval: оценка кандидата
        - baseline_eval: оценка baseline
        - mode: режим оптимизации

        RETURNS:
        - float: величина улучшения (положительная = улучшение)
        """
        if mode == OptimizationMode.SPEED:
            if baseline_eval.latency <= 0:
                return 0.0
            improvement = (baseline_eval.latency - candidate_eval.latency) / baseline_eval.latency
        elif mode == OptimizationMode.TOKENS:
            if baseline_eval.latency <= 0:
                return 0.0
            improvement = (baseline_eval.latency - candidate_eval.latency) / baseline_eval.latency
        elif mode == OptimizationMode.BALANCED:
            accuracy_improvement = candidate_eval.score - baseline_eval.score
            latency_norm = 0.0
            if baseline_eval.latency > 0:
                latency_norm = (baseline_eval.latency - candidate_eval.latency) / baseline_eval.latency
            improvement = 0.7 * accuracy_improvement + 0.3 * max(latency_norm, 0)
        else:
            improvement = candidate_eval.score - baseline_eval.score

        return improvement

    async def _evaluate_version(
        self,
        version: PromptVersion,
        capability: str,
    ) -> EvaluationResult:
        """
        Оценка версии через реальный бенчмарк.

        ARGS:
        - version: версия для оценки
        - capability: название способности

        RETURNS:
        - EvaluationResult: оценка
        """
        if not self.executor_callback:
            return EvaluationResult(version_id=version.id, success_rate=0.0, score=0.0)

        # Загрузка сценариев для capability
        scenarios = await self._load_scenarios_for_version(version, capability)

        if not scenarios:
            return EvaluationResult(version_id=version.id, success_rate=0.0, score=0.0)

        # Запуск бенчмарка
        benchmark_results = await self.benchmark_runner.run(version, scenarios)

        # Оценка через Evaluator
        evaluation = self.evaluator.evaluate(version.id, benchmark_results)

        return evaluation

    async def _evaluate_version_with_baseline(
        self,
        version: PromptVersion,
        capability: str,
        baseline_results: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        Оценка версии с использованием предварительных результатов baseline.

        Если version.id содержит 'baseline', используем предварительно
        рассчитанные результаты из baseline_results вместо запуска бенчмарка.

        ARGS:
        - version: версия для оценки
        - capability: название способности
        - baseline_results: предварительные результаты baseline из CLI

        RETURNS:
        - EvaluationResult: оценка
        """
        # Если это baseline версия и есть предварительные результаты — используем их
        if baseline_results and 'baseline' in version.id.lower():
            print(f"  📊 [Evaluate] Используем предварительные baseline результаты")

            # Маппим результаты из baseline benchmark в EvaluationResult
            success_rate = baseline_results.get('success_rate', 0.0)
            latency = baseline_results.get('latency', 0.0)
            # Если есть avg_steps, используем как latency (мс)
            if latency == 0 and 'avg_steps' in baseline_results:
                latency = baseline_results.get('avg_steps', 0)

            # Вычисляем score по формуле evaluator
            # score = success_rate * 0.4 + execution_success * 0.3 + sql_validity * 0.2 - latency * 0.1
            score = success_rate * 0.4  # execution_success=0.0 (нет успешных), sql_validity=1.0, latency=0

            return EvaluationResult(
                version_id=version.id,
                success_rate=success_rate,
                score=score,
                latency=latency,
                execution_success=1.0 if success_rate > 0 else 0.0,
                sql_validity=1.0,
                error_rate=1.0 - success_rate,
            )

        # Для остальных версий — стандартная оценка через бенчмарк
        return await self._evaluate_version(version, capability)

    async def _load_scenarios_for_version(
        self,
        version: PromptVersion,
        capability: str,
    ) -> List[BenchmarkScenario]:
        """
        Загрузка сценариев бенчмарка для capability.

        ИСПОЛЬЗУЕТ реальные benchmark questions из data/benchmarks/agent_benchmark.json,
        а не traces — чтобы оценивать на НЕЗАВИСИМЫХ данных.

        ARGS:
        - version: версия промпта
        - capability: название способности

        RETURNS:
        - List[BenchmarkScenario]: список сценариев
        """
        try:
            # Попытка загрузить реальные benchmark questions
            scenarios = await self._load_real_benchmark_scenarios(capability)
            if scenarios:
                print(f"  📊 [Scenarios] Загружено {len(scenarios)} реальных benchmark сценариев")
                return scenarios

            # Fallback: строим из traces
            print(f"  ⚠️ [Scenarios] Benchmark не найден, строим из traces...")
            traces = await self.trace_collector.collect_traces(capability)
            if not traces:
                print(f"  ⚠️ [Scenarios] Нет traces для {capability}")
                return []

            print(f"  📊 [Scenarios] Traces собрано: {len(traces)}, строим dataset...")
            dataset = await self.trace_collector.build_dataset(capability)
            print(f"  📊 [Scenarios] Dataset samples: {len(dataset.samples)}")

            scenario_builder = ScenarioBuilder()
            scenarios = await scenario_builder.build(dataset)
            print(f"  📊 [Scenarios] Сценариев построено: {len(scenarios)}")
            return scenarios
        except Exception as e:
            import traceback
            print(f"  ❌ [Scenarios] Ошибка: {e}")
            print(f"  Traceback: {traceback.format_exc()}")
            return []

    async def _load_real_benchmark_scenarios(
        self,
        capability: str,
    ) -> List[BenchmarkScenario]:
        """
        Загрузка реальных benchmark сценариев из JSON файла.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[BenchmarkScenario]: список сценариев или []
        """
        import json
        from pathlib import Path

        benchmark_file = Path('data/benchmarks/agent_benchmark.json')
        if not benchmark_file.exists():
            return []

        with open(benchmark_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        test_cases = data.get('levels', {}).get('sql_generation', {}).get('test_cases', [])
        if not test_cases:
            return []

        scenarios = []
        limit = self.config.benchmark_size
        for tc in test_cases[:limit]:
            scenario = BenchmarkScenario(
                id=f"bench_{tc.get('id', 'unknown')}",
                name=f"{capability}_bench_{tc.get('id', 'unknown')}",
                description=tc.get('description', tc.get('input', '')),
                goal=tc['input'],
                expected_output=ExpectedOutput(
                    content=tc.get('expected_sql', tc.get('expected_answer', '')),
                    criteria=[
                        EvaluationCriterion(
                            name='sql_match',
                            evaluation_type=EvaluationType.EXACT_MATCH,
                            weight=0.7,
                            description='SQL-запрос должен совпадать с ожидаемым',
                        ),
                        EvaluationCriterion(
                            name='answer_validity',
                            evaluation_type=EvaluationType.COVERAGE,
                            weight=0.3,
                            description='Ответ должен содержать релевантную информацию',
                        ),
                    ],
                ),
                timeout_seconds=120,
                metadata={
                    'source': 'benchmark',
                    'expected_sql': tc.get('expected_sql'),
                    'validation': tc.get('validation'),
                },
            )
            scenarios.append(scenario)

        return scenarios

    def get_optimization_report(self, result: Optional[OptimizationResult]) -> Dict[str, Any]:
        """
        Получение отчёта об оптимизации.

        ARGS:
        - result: результат оптимизации

        RETURNS:
        - Dict[str, Any]: отчёт
        """
        if not result:
            return {"status": "failed"}

        return {
            "status": result.status,
            "capability": result.capability,
            "from_version": result.from_version,
            "to_version": result.to_version,
            "iterations": result.iterations,
            "target_achieved": result.target_achieved,
            "initial_metrics": result.initial_metrics,
            "final_metrics": result.final_metrics,
            "improvements": result.improvements,
            "error": result.error,
            "timestamp": result.timestamp.isoformat(),
        }

    async def _publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
    ) -> None:
        """
        Публикация события через event_bus.

        ARGS:
        - event_type: тип события
        - data: данные события
        """
        await self.event_bus.publish(
            event_type,
            data=data,
            source="OptimizationOrchestrator",
        )
