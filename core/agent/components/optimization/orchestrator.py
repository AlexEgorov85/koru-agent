"""
OptimizationOrchestrator — оркестрация с полным анализом traces.

ОТВЕТСТВЕННОСТЬ:
- Оркестрация всех компонентов оптимизации
- Анализ execution traces
- Поиск корневых причин
- Умная генерация улучшений

ПИПЛАЙН:
1. traces = trace_collector.collect_traces()
2. patterns = pattern_analyzer.analyze(traces)
3. prompt_issues = prompt_analyzer.analyze_prompts(traces)
4. root_causes = root_cause_analyzer.analyze(...)
5. examples = example_extractor.extract_good_examples(traces)
6. candidates = prompt_generator.generate_improvements(root_causes, examples)
7. test + evaluate + safety check → promote
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass

from core.services.benchmarks.benchmark_models import (
    PromptVersion,
    EvaluationResult,
    OptimizationResult,
    OptimizationMode,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

from .trace_collector import TraceCollector
from .pattern_analyzer import PatternAnalyzer
from .prompt_analyzer import PromptResponseAnalyzer
from .root_cause_analyzer import RootCauseAnalyzer
from .example_extractor import ExampleExtractor
from .evaluator import Evaluator
from .prompt_generator import PromptGenerator
from .version_manager import VersionManager
from .safety_layer import SafetyLayer

# BenchmarkRunner импортируется из core.benchmarks
from core.services.benchmarks.benchmark_runner import BenchmarkRunner


@dataclass
class OrchestratorV2Config:
    """Конфигурация OptimizationOrchestrator v2"""
    max_iterations: int = 3
    target_accuracy: float = 0.9
    min_improvement: float = 0.05
    timeout_seconds: int = 600
    max_examples: int = 5
    max_error_examples: int = 3


class OptimizationOrchestrator:
    """
    Оркестратор цикла оптимизации промптов.

    RESPONSIBILITIES:
    - Координация компонентов оптимизации
    - Анализ execution traces
    - Поиск корневых причин проблем
    - Генерация целевых улучшений

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

        self.event_bus_logger = EventBusLogger(
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            event_bus,
            session_id="system",
            agent_id="system",
            component="OptimizationOrchestrator"
        )

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
    ) -> Optional[OptimizationResult]:
        """
        Запуск цикла оптимизации.

        ЭТАПЫ:
        1. Сбор traces
        2. Анализ паттернов
        3. Анализ промптов/ответов
        4. Поиск корневых причин
        5. Извлечение примеров
        6. Генерация улучшений
        7. Тестирование и оценка

        ARGS:
        - capability: название способности
        - mode: режим оптимизации

        RETURNS:
        - Optional[OptimizationResult]: результат или None
        """
        await self.event_bus_logger.info(
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"Запуск оптимизации v2 для {capability}"
        )

        start_time = datetime.now()

        try:
            # ЭТАП 1: Сбор traces
            await self.event_bus_logger.info("ЭТАП 1: Сбор execution traces...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            traces = await self.trace_collector.collect_traces(capability)

            if not traces:
                await self.event_bus_logger.warning(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Не найдено traces для {capability}"
                )
                return None

            await self.event_bus_logger.info(f"Собрано {len(traces)} traces")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # ЭТАП 2: Анализ паттернов
            await self.event_bus_logger.info("ЭТАП 2: Анализ паттернов...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            patterns = self.pattern_analyzer.analyze(traces)
            pattern_stats = self.pattern_analyzer.get_pattern_stats(patterns)
            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Найдено {pattern_stats['total_patterns']} паттернов"
            )

            # ЭТАП 3: Анализ промптов и ответов
            await self.event_bus_logger.info("ЭТАП 3: Анализ промптов/ответов...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            prompt_issues = self.prompt_analyzer.analyze_prompts(traces)
            response_issues = self.prompt_analyzer.analyze_responses(traces)
            analysis_stats = self.prompt_analyzer.get_analysis_stats(
                prompt_issues, response_issues
            )
            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Найдено {analysis_stats['total_prompt_issues']} проблем промптов, "
                f"{analysis_stats['total_response_issues']} проблем ответов"
            )

            # ЭТАП 4: Поиск корневых причин
            await self.event_bus_logger.info("ЭТАП 4: Поиск корневых причин...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            root_causes = self.root_cause_analyzer.analyze(
                patterns, prompt_issues, response_issues
            )
            cause_stats = self.root_cause_analyzer.get_root_cause_stats(root_causes)
            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Найдено {cause_stats['total_root_causes']} корневых причин"
            )

            # ЭТАП 5: Извлечение примеров
            await self.event_bus_logger.info("ЭТАП 5: Извлечение примеров...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            good_examples, error_examples = self.example_extractor.extract_few_shot_examples(
                traces,
                capability,
                num_good=self.config.max_examples,
                num_bad=self.config.max_error_examples
            )
            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Извлечено {len(good_examples)} хороших примеров, "
                f"{len(error_examples)} примеров ошибок"
            )

            # ЭТАП 6: Получение baseline и генерация улучшений
            await self.event_bus_logger.info("ЭТАП 6: Генерация улучшений...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            baseline = await self.version_manager.get_active(capability)

            if not baseline:
                await self.event_bus_logger.error(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Baseline версия не найдена для {capability}"
                )
                return None

            candidates = await self.prompt_generator.generate_improvements(
                original_prompt=baseline,
                root_causes=root_causes,
                good_examples=good_examples,
                error_examples=error_examples
            )

            if not candidates:
                await self.event_bus_logger.warning("Кандидаты не сгенерированы")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return None

            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Сгенерировано {len(candidates)} кандидатов"
            )

            # ЭТАП 7: Тестирование и оценка
            await self.event_bus_logger.info("ЭТАП 7: Тестирование кандидатов...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            result = await self._test_and_evaluate(
                capability=capability,
                baseline=baseline,
                candidates=candidates,
                mode=mode
            )

            elapsed = (datetime.now() - start_time).total_seconds()
            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Оптимизация завершена за {elapsed:.1f}с"
            )

            return result

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка оптимизации: {e}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return None

    async def _test_and_evaluate(
        self,
        capability: str,
        baseline: PromptVersion,
        candidates: List[PromptVersion],
        mode: OptimizationMode
    ) -> Optional[OptimizationResult]:
        """
        Тестирование и оценка кандидатов.

        ARGS:
        - capability: название способности
        - baseline: baseline версия
        - candidates: кандидаты
        - mode: режим оптимизации

        RETURNS:
        - Optional[OptimizationResult]: результат
        """
        if not self.executor_callback:
            await self.event_bus_logger.error("Executor callback не установлен")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return None

        # Оценка baseline
        baseline_eval = await self._evaluate_version(baseline)

        # Инициализация результата
        result = OptimizationResult(
            capability=capability,
            from_version=baseline.id,
            to_version=baseline.id,
            mode=mode,
            iterations=0,
            initial_metrics={
                'success_rate': baseline_eval.success_rate,
                'score': baseline_eval.score
            }
        )

        current_best = baseline
        current_best_eval = baseline_eval

        # Тестирование кандидатов
        for iteration, candidate in enumerate(candidates[:self.config.max_iterations]):
            result.iterations = iteration + 1

            await self.event_bus_logger.info(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Тестирование кандидата {iteration + 1}/{len(candidates)}"
            )

            # Регистрация кандидата
            await self.version_manager.register(candidate)

            # Оценка кандидата
            candidate_eval = await self._evaluate_version(candidate)

            # Проверка улучшения
            improvement = candidate_eval.score - current_best_eval.score

            if improvement >= self.config.min_improvement:
                # Проверка безопасности
                is_safe, checks = await self.safety_layer.check(
                    candidate_eval, current_best_eval
                )

                if is_safe:
                    # Улучшение найдено и безопасно
                    current_best = candidate
                    current_best_eval = candidate_eval
                    result.to_version = candidate.id
                    result.final_metrics = {
                        'success_rate': candidate_eval.success_rate,
                        'score': candidate_eval.score
                    }

                    # Продвижение версии
                    await self.version_manager.promote(candidate.id, capability)

                    await self.event_bus_logger.info(
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"Улучшение найдено: score {candidate_eval.score:.3f} "
                        f"(+{improvement:.3f})"
                    )

                    # Проверка достижения цели
                    if candidate_eval.success_rate >= self.config.target_accuracy:
                        result.target_achieved = True
                        await self.event_bus_logger.info("Цель достигнута")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        break
                else:
                    await self.event_bus_logger.warning(
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"Кандидат {candidate.id} отклонён safety layer"
                    )
                    await self.version_manager.reject(
                        candidate.id, capability, "Safety check failed"
                    )
            else:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Улучшение недостаточно: {improvement:.3f}"
                )
                await self.version_manager.reject(
                    candidate.id, capability, "Insufficient improvement"
                )

        # Расчёт улучшений
        result.calculate_improvements()

        return result

    async def _evaluate_version(
        self,
        version: PromptVersion
    ) -> EvaluationResult:
        """
        Оценка версии.

        ARGS:
        - version: версия для оценки

        RETURNS:
        - EvaluationResult: оценка
        """
        if not self.executor_callback:
            return EvaluationResult(
                version_id=version.id,
                success_rate=0.8,
                score=0.7
            )

        # Запуск бенчмарка (упрощённо)
        # В реальной реализации нужно загружать сценарии
        from core.services.benchmarks.benchmark_models import BenchmarkRunResult

        # Mock результаты для примера
        mock_results = [
            BenchmarkRunResult(
                version_id=version.id,
                scenario_id=f"s{i}",
                success=True,
                execution_time_ms=100
            )
            for i in range(5)
        ]

        return self.evaluator.evaluate(version.id, mock_results)

    def get_optimization_report(self, result: Optional[OptimizationResult]) -> Dict[str, Any]:
        """
        Получение отчёта об оптимизации.

        ARGS:
        - result: результат оптимизации

        RETURNS:
        - Dict[str, Any]: отчёт
        """
        if not result:
            return {'status': 'failed'}

        return {
            'status': 'completed',
            'capability': result.capability,
            'from_version': result.from_version,
            'to_version': result.to_version,
            'iterations': result.iterations,
            'target_achieved': result.target_achieved,
            'initial_metrics': result.initial_metrics,
            'final_metrics': result.final_metrics,
            'improvements': result.improvements,
            'timestamp': result.timestamp.isoformat()
        }
