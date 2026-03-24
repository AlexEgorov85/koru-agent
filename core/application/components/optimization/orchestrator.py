"""
OptimizationOrchestrator - оркестрация цикла оптимизации.

ОТВЕТСТВЕННОСТЬ:
- Оркестрация всех компонентов оптимизации
- Управление пайплайном оптимизации
- Делегирование задач компонентам
- Отсутствие бизнес-логики (только координация)

ПИПЛАЙН:
1. dataset = dataset_builder.build()
2. scenarios = scenario_builder.build(dataset)
3. baseline = version_manager.get_active()
4. candidates = prompt_generator.generate(baseline)
5. results = benchmark_runner.run(candidates, scenarios)
6. evaluated = evaluator.evaluate(results)
7. best = evaluator.select_best(evaluated)
8. if safety.check(best, baseline): version_manager.promote(best)
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass

from core.models.data.benchmark import (
    BenchmarkDataset,
    BenchmarkScenario,
    PromptVersion,
    EvaluationResult,
    FailureAnalysis,
    OptimizationResult,
    OptimizationMode,
    ScenarioType,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging import EventBusLogger

from .dataset_builder import DatasetBuilder
from .scenario_builder import ScenarioBuilder
from .benchmark_runner import BenchmarkRunner
from .evaluator import Evaluator
from .prompt_generator import PromptGenerator
from .version_manager import VersionManager
from .safety_layer import SafetyLayer


@dataclass
class OrchestratorConfig:
    """Конфигурация OptimizationOrchestrator"""
    max_iterations: int = 5
    target_accuracy: float = 0.9
    min_improvement: float = 0.05  # 5% минимальное улучшение
    timeout_seconds: int = 300
    parallel_candidates: int = 1


class OptimizationOrchestrator:
    """
    Оркестратор цикла оптимизации промптов.

    RESPONSIBILITIES:
    - Координация компонентов оптимизации
    - Управление итерациями
    - Публикация событий
    - Логирование процесса

    THIS IS NOT A GOD OBJECT:
    - Вся бизнес-логика делегирована компонентам
    - Этот класс только координирует работу
    - Любой компонент заменяем без изменений orchestrator

    USAGE:
    ```python
    orchestrator = OptimizationOrchestrator(
        dataset_builder, scenario_builder, benchmark_runner,
        evaluator, prompt_generator, version_manager, safety_layer
    )
    result = await orchestrator.optimize(capability, mode)
    ```
    """

    def __init__(
        self,
        dataset_builder: DatasetBuilder,
        scenario_builder: ScenarioBuilder,
        benchmark_runner: BenchmarkRunner,
        evaluator: Evaluator,
        prompt_generator: PromptGenerator,
        version_manager: VersionManager,
        safety_layer: SafetyLayer,
        event_bus: UnifiedEventBus,
        config: Optional[OrchestratorConfig] = None
    ):
        """
        Инициализация OptimizationOrchestrator.

        ARGS:
        - dataset_builder: построитель датасета
        - scenario_builder: построитель сценариев
        - benchmark_runner: раннер бенчмарков
        - evaluator: оценщик качества
        - prompt_generator: генератор промптов
        - version_manager: менеджер версий
        - safety_layer: слой безопасности
        - event_bus: шина событий
        - config: конфигурация
        """
        self.dataset_builder = dataset_builder
        self.scenario_builder = scenario_builder
        self.benchmark_runner = benchmark_runner
        self.evaluator = evaluator
        self.prompt_generator = prompt_generator
        self.version_manager = version_manager
        self.safety_layer = safety_layer
        self.event_bus = event_bus
        self.config = config or OrchestratorConfig()

        self.event_bus_logger = EventBusLogger(
            event_bus,
            session_id="system",
            agent_id="system",
            component="OptimizationOrchestrator"
        )

        # Callback для выполнения промптов (инжектируется извне)
        self.executor_callback: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None

    def set_executor_callback(
        self,
        callback: Callable[[str, str], Awaitable[Dict[str, Any]]]
    ) -> None:
        """
        Установка callback для выполнения промптов.

        ARGS:
        - callback: async функция (input, version_id) -> result
        """
        self.executor_callback = callback

    async def optimize(
        self,
        capability: str,
        mode: OptimizationMode = OptimizationMode.ACCURACY,
        failure_analysis: Optional[FailureAnalysis] = None
    ) -> Optional[OptimizationResult]:
        """
        Запуск цикла оптимизации.

        ЭТО ГЛАВНЫЙ МЕТОД который оркестрирует весь процесс.

        ARGS:
        - capability: название способности для оптимизации
        - mode: режим оптимизации
        - failure_analysis: анализ неудач (опционально, создаётся если не предоставлен)

        RETURNS:
        - Optional[OptimizationResult]: результат оптимизации или None
        """
        await self.event_bus_logger.info(
            f"Запуск оптимизации для {capability} (режим: {mode.value})"
        )

        # Публикация события начала
        await self._publish_optimization_start(capability, mode)

        start_time = datetime.now()

        try:
            # ЭТАП 1: Построение датасета
            dataset = await self.dataset_builder.build(capability)
            await self.event_bus_logger.info(
                f"Датасет построен: {dataset.size} образцов"
            )

            # ЭТАП 2: Построение сценариев
            scenarios = await self.scenario_builder.build(dataset)
            await self.event_bus_logger.info(
                f"Сценарии построены: {len(scenarios)} сценариев"
            )

            # ЭТАП 3: Получение baseline версии
            baseline = await self.version_manager.get_active(capability)
            if not baseline:
                await self.event_bus_logger.error(
                    f"Baseline версия не найдена для {capability}"
                )
                return None

            baseline_eval = await self._evaluate_baseline(baseline, scenarios)

            # ЭТАП 4-8: Цикл оптимизации
            result = await self._optimization_loop(
                capability=capability,
                baseline=baseline,
                baseline_eval=baseline_eval,
                scenarios=scenarios,
                mode=mode,
                failure_analysis=failure_analysis
            )

            # Публикация события завершения
            await self._publish_optimization_complete(result)

            elapsed = (datetime.now() - start_time).total_seconds()
            await self.event_bus_logger.info(
                f"Оптимизация завершена за {elapsed:.1f}с: "
                f"{result.from_version} → {result.to_version}"
            )

            return result

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка оптимизации: {e}")
            await self._publish_optimization_error(capability, mode, str(e))
            return None

    async def _optimization_loop(
        self,
        capability: str,
        baseline: PromptVersion,
        baseline_eval: EvaluationResult,
        scenarios: List[BenchmarkScenario],
        mode: OptimizationMode,
        failure_analysis: Optional[FailureAnalysis]
    ) -> OptimizationResult:
        """
        Цикл оптимизации с итерациями.

        ARGS:
        - capability: название способности
        - baseline: baseline версия
        - baseline_eval: оценка baseline
        - scenarios: сценарии для тестирования
        - mode: режим оптимизации
        - failure_analysis: анализ неудач

        RETURNS:
        - OptimizationResult: результат оптимизации
        """
        result = OptimizationResult(
            capability=capability,
            from_version=baseline.id,
            to_version=baseline.id,
            mode=mode,
            iterations=0,
            initial_metrics={
                'success_rate': baseline_eval.success_rate,
                'score': baseline_eval.score,
                'error_rate': baseline_eval.error_rate
            }
        )

        current_best = baseline
        current_best_eval = baseline_eval

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            await self.event_bus_logger.info(
                f"Итерация {iteration + 1}/{self.config.max_iterations}"
            )

            # Генерация кандидатов
            candidates = await self.prompt_generator.generate(
                parent=current_best,
                failure_analysis=failure_analysis or FailureAnalysis(
                    capability=capability,
                    version=current_best.id
                )
            )

            if not candidates:
                await self.event_bus_logger.warning("Кандидаты не сгенерированы")
                break

            # Регистрация кандидатов
            for candidate in candidates:
                await self.version_manager.register(candidate)

            # Тестирование кандидатов
            best_candidate, best_eval = await self._test_candidates(
                candidates, scenarios, current_best_eval
            )

            if not best_candidate:
                await self.event_bus_logger.info("Лучший кандидат не найден")
                break

            # Проверка безопасности
            is_safe, checks = await self.safety_layer.check(best_eval, current_best_eval)

            if not is_safe:
                # Отклонение опасного кандидата
                await self.version_manager.reject(
                    best_candidate.id,
                    capability,
                    reason="Safety check failed"
                )
                await self.event_bus_logger.warning(
                    f"Кандидат {best_candidate.id} отклонён safety layer"
                )
                break  # Прекращаем итерации

            # Проверка улучшения
            improvement = best_eval.score - current_best_eval.score

            if improvement >= self.config.min_improvement:
                # Улучшение найдено
                current_best = best_candidate
                current_best_eval = best_eval
                result.to_version = best_candidate.id
                result.final_metrics = {
                    'success_rate': best_eval.success_rate,
                    'score': best_eval.score,
                    'error_rate': best_eval.error_rate
                }

                # Продвижение версии
                await self.version_manager.promote(best_candidate.id, capability)

                await self.event_bus_logger.info(
                    f"Улучшение найдено: score {best_eval.score:.3f} "
                    f"(+{improvement:.3f})"
                )

                # Проверка достижения цели
                if best_eval.success_rate >= self.config.target_accuracy:
                    result.target_achieved = True
                    await self.event_bus_logger.info("Цель оптимизации достигнута")
                    break
            else:
                await self.event_bus_logger.info(
                    f"Улучшение недостаточно: {improvement:.3f}"
                )
                # Отклонение кандидата
                await self.version_manager.reject(
                    best_candidate.id,
                    capability,
                    reason="Insufficient improvement"
                )
                break  # Прекращаем итерации

        # Расчёт улучшений
        result.calculate_improvements()

        return result

    async def _test_candidates(
        self,
        candidates: List[PromptVersion],
        scenarios: List[BenchmarkScenario],
        baseline_eval: EvaluationResult
    ) -> tuple:
        """
        Тестирование кандидатов.

        ARGS:
        - candidates: список кандидатов
        - scenarios: сценарии для тестирования
        - baseline_eval: оценка baseline для сравнения

        RETURNS:
        - tuple: (лучший кандидат, оценка лучшего)
        """
        if not self.executor_callback:
            await self.event_bus_logger.error("Executor callback не установлен")
            return None, None

        evaluations = []

        for candidate in candidates:
            # Запуск бенчмарка
            run_results = await self.benchmark_runner.run(candidate, scenarios)

            # Оценка
            evaluation = self.evaluator.evaluate(candidate.id, run_results)
            evaluations.append((candidate, evaluation))

        if not evaluations:
            return None, None

        # Селекция лучшего
        best_candidate, best_eval = max(evaluations, key=lambda x: x[1].score)

        return best_candidate, best_eval

    async def _evaluate_baseline(
        self,
        baseline: PromptVersion,
        scenarios: List[BenchmarkScenario]
    ) -> EvaluationResult:
        """
        Оценка baseline версии.

        ARGS:
        - baseline: baseline версия
        - scenarios: сценарии для тестирования

        RETURNS:
        - EvaluationResult: оценка baseline
        """
        if not self.executor_callback:
            # Возвращаем дефолтную оценку если нет executor
            return EvaluationResult(
                version_id=baseline.id,
                success_rate=0.8,
                score=0.7
            )

        run_results = await self.benchmark_runner.run(baseline, scenarios)
        return self.evaluator.evaluate(baseline.id, run_results)

    async def _publish_optimization_start(
        self,
        capability: str,
        mode: OptimizationMode
    ) -> None:
        """Публикация события начала оптимизации"""
        await self.event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_STARTED,
            data={
                'capability': capability,
                'mode': mode.value,
                'target_accuracy': self.config.target_accuracy,
                'timestamp': datetime.now().isoformat()
            }
        )

    async def _publish_optimization_complete(
        self,
        result: Optional[OptimizationResult]
    ) -> None:
        """Публикация события завершения оптимизации"""
        if not result:
            return

        await self.event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            data={
                'capability': result.capability,
                'from_version': result.from_version,
                'to_version': result.to_version,
                'iterations': result.iterations,
                'improvements': result.improvements,
                'target_achieved': result.target_achieved,
                'timestamp': result.timestamp.isoformat()
            }
        )

    async def _publish_optimization_error(
        self,
        capability: str,
        mode: OptimizationMode,
        error: str
    ) -> None:
        """Публикация события ошибки оптимизации"""
        await self.event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                'capability': capability,
                'mode': mode.value,
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
        )

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """
        Получение статистики пайплайна.

        RETURNS:
        - Dict[str, Any]: статистика компонентов
        """
        return {
            'dataset_builder': {
                'config': {
                    'min_samples': self.dataset_builder.config.min_samples,
                    'min_failure_rate': self.dataset_builder.config.min_failure_rate
                }
            },
            'scenario_builder': {
                'config': {
                    'min_type_percentage': self.scenario_builder.config.min_type_percentage,
                    'min_failure_percentage': self.scenario_builder.config.min_failure_percentage
                }
            },
            'benchmark_runner': {
                'config': {
                    'temperature': self.benchmark_runner.config.temperature,
                    'seed': self.benchmark_runner.config.seed
                }
            },
            'evaluator': {
                'config': {
                    'success_rate_weight': self.evaluator.config.success_rate_weight,
                    'min_success_rate': self.evaluator.config.min_success_rate
                }
            },
            'prompt_generator': {
                'diversity_stats': self.prompt_generator.get_diversity_stats()
            },
            'safety_layer': {
                'stats': self.safety_layer.get_stats()
            }
        }
