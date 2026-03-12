"""
Сервис бенчмарков (Benchmark Service).

КОМПОНЕНТЫ:
- BenchmarkService: оркестрация бенчмарков

FEATURES:
- Запуск бенчмарков по сценариям
- Сбор метрик выполнения
- Сравнение версий промптов/контрактов
- Автоматическое продвижение версий при улучшении метрик
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from core.models.data.benchmark import (
    BenchmarkScenario,
    BenchmarkResult,
    ExpectedOutput,
    ActualOutput,
    EvaluationCriterion,
    CriterionScore,
    VersionComparison,
    AccuracyEvaluation,
)
from core.application.services.accuracy_evaluator import (
    AccuracyEvaluatorService,
    EvaluationResult,
)
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging import EventBusLogger


@dataclass
class BenchmarkConfig:
    """Конфигурация бенчмарка"""
    max_iterations: int = 10
    target_accuracy: float = 0.9
    timeout_seconds: int = 60
    parallel_runs: int = 1


class BenchmarkService:
    """
    Сервис бенчмарков для оценки качества агента.

    RESPONSIBILITIES:
    - Запуск бенчмарков по сценариям
    - Сбор метрик выполнения
    - Сравнение версий промптов/контрактов
    - Автоматическое продвижение версий при улучшении

    USAGE:
    ```python
    service = BenchmarkService(metrics_collector, accuracy_evaluator, event_bus)
    result = await service.run_benchmark(scenario, version)
    comparison = await service.compare_versions('cap', 'v1.0', 'v2.0', [scenario])
    ```
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        accuracy_evaluator: AccuracyEvaluatorService,
        event_bus: UnifiedEventBus,
        config: Optional[BenchmarkConfig] = None
    ):
        """
        Инициализация сервиса бенчмарков.

        ARGS:
        - metrics_collector: сборщик метрик
        - accuracy_evaluator: сервис оценки точности
        - event_bus: шина событий
        - config: конфигурация бенчмарка
        """
        self.metrics_collector = metrics_collector
        self.accuracy_evaluator = accuracy_evaluator
        self.event_bus = event_bus
        self.config = config or BenchmarkConfig()
        self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="BenchmarkService")

    async def run_benchmark(
        self,
        scenario: BenchmarkScenario,
        version: str,
        agent_executor=None
    ) -> BenchmarkResult:
        """
        Запуск бенчмарка по сценарию.

        ARGS:
        - scenario: сценарий бенчмарка
        - version: версия промпта/контракта для тестирования
        - agent_executor: функция для выполнения агента (опционально)

        RETURNS:
        - BenchmarkResult: результат бенчмарка

        PROCESS:
        1. Публикация события BENCHMARK_STARTED
        2. Выполнение сценария
        3. Оценка результата через AccuracyEvaluator
        4. Публикация события BENCHMARK_COMPLETED
        """
        await self.event_bus_logger.info(f"Запуск бенчмарка: {scenario.name} (версия {version})")

        # Публикация события начала бенчмарка
        await self._publish_benchmark_start(scenario, version)

        start_time = datetime.now()

        try:
            # Выполнение сценария
            actual_output = await self._execute_scenario(scenario, version, agent_executor)

            # Оценка результата
            scores = await self._evaluate_result(scenario, actual_output)

            # Расчёт общей оценки
            overall_score = self._calculate_overall_score(scores)

            # Определение успешности
            success = self._determine_success(scores, overall_score, scenario)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Создание результата
            result = BenchmarkResult(
                scenario_id=scenario.id,
                versions={scenario.name: version},
                success=success,
                scores=scores,
                overall_score=overall_score,
                actual_output=actual_output,
                execution_time_ms=execution_time,
                tokens_used=actual_output.tokens_used if actual_output else 0,
                timestamp=datetime.now()
            )

            # Публикация события завершения
            await self._publish_benchmark_complete(result)

            await self.event_bus_logger.info(f"Бенчмарк завершён: {scenario.name} (успех={success}, score={overall_score:.2f})")

            return result

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка бенчмарка {scenario.name}: {e}")

            # Публикация события ошибки
            await self._publish_benchmark_failed(scenario, version, str(e))

            return BenchmarkResult(
                scenario_id=scenario.id,
                versions={scenario.name: version},
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                timestamp=datetime.now()
            )

    async def compare_versions(
        self,
        capability: str,
        version_a: str,
        version_b: str,
        scenarios: List[BenchmarkScenario],
        agent_executor=None
    ) -> VersionComparison:
        """
        Сравнение двух версий промпта/контракта.

        ARGS:
        - capability: название способности
        - version_a: первая версия (baseline)
        - version_b: вторая версия (candidate)
        - scenarios: список сценариев для сравнения
        - agent_executor: функция для выполнения агента

        RETURNS:
        - VersionComparison: результат сравнения
        """
        await self.event_bus_logger.info(f"Сравнение версий: {version_a} vs {version_b} для {capability}")

        # Запуск бенчмарков для обеих версий
        results_a = []
        results_b = []

        for scenario in scenarios:
            result_a = await self.run_benchmark(scenario, version_a, agent_executor)
            result_b = await self.run_benchmark(scenario, version_b, agent_executor)

            results_a.append(result_a)
            results_b.append(result_b)

        # Агрегация метрик
        metrics_a = self._aggregate_metrics(results_a)
        metrics_b = self._aggregate_metrics(results_b)

        # Создание сравнения
        comparison = VersionComparison(
            capability=capability,
            version_a=version_a,
            version_b=version_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b
        )

        # Расчёт улучшения
        comparison.calculate_improvement('accuracy')

        # Статистическая значимость (простая проверка)
        comparison.statistically_significant = self._check_statistical_significance(results_a, results_b)

        comparison.details = f"Сравнение по {len(scenarios)} сценариям"

        await self.event_bus_logger.info(f"Сравнение завершено: победитель={comparison.winner}, улучшение={comparison.improvement:.1f}%")

        return comparison

    async def promote_version(
        self,
        capability: str,
        from_version: str,
        to_version: str,
        reason: str = ""
    ) -> bool:
        """
        Продвижение версии (promotion).

        ARGS:
        - capability: название способности
        - from_version: текущая активная версия
        - to_version: новая версия для продвижения
        - reason: причина продвижения

        RETURNS:
        - bool: успешно ли продвижение
        """
        await self.event_bus_logger.info(f"Продвижение версии: {from_version} → {to_version} для {capability}")

        try:
            # Публикация события
            await self.event_bus.publish(
                EventType.VERSION_PROMOTED,
                data={
                    'capability': capability,
                    'from_version': from_version,
                    'to_version': to_version,
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Обновление registry (через callback если предоставлен)
            if hasattr(self, '_on_version_promoted'):
                await self._on_version_promoted(capability, from_version, to_version)

            await self.event_bus_logger.info(f"Версия {to_version} продвинута для {capability}")
            return True

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка продвижения версии: {e}")
            return False

    async def reject_version(
        self,
        capability: str,
        version: str,
        reason: str = ""
    ) -> bool:
        """
        Отклонение версии.

        ARGS:
        - capability: название способности
        - version: версия для отклонения
        - reason: причина отклонения

        RETURNS:
        - bool: успешно ли отклонение
        """
        await self.event_bus_logger.info(f"Отклонение версии: {version} для {capability}")

        try:
            await self.event_bus.publish(
                EventType.VERSION_REJECTED,
                data={
                    'capability': capability,
                    'version': version,
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }
            )

            await self.event_bus_logger.info(f"Версия {version} отклонена для {capability}")
            return True

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка отклонения версии: {e}")
            return False

    async def auto_promote_if_better(
        self,
        capability: str,
        candidate_version: str,
        current_version: str,
        scenarios: List[BenchmarkScenario],
        metric_threshold: float = 0.05,
        agent_executor=None
    ) -> bool:
        """
        Автоматическое продвижение версии если метрики лучше.

        ARGS:
        - capability: название способности
        - candidate_version: версия-кандидат
        - current_version: текущая версия
        - scenarios: сценарии для сравнения
        - metric_threshold: минимальное улучшение (5% по умолчанию)
        - agent_executor: функция выполнения агента

        RETURNS:
        - bool: продвинута ли версия
        """
        await self.event_bus_logger.info(f"Автоматическая проверка продвижения: {candidate_version} vs {current_version}")

        # Сравнение версий
        comparison = await self.compare_versions(
            capability,
            current_version,
            candidate_version,
            scenarios,
            agent_executor
        )

        # Проверка улучшения
        if comparison.winner == candidate_version and comparison.improvement >= metric_threshold * 100:
            reason = f"Улучшение accuracy на {comparison.improvement:.1f}%"
            success = await self.promote_version(
                capability,
                current_version,
                candidate_version,
                reason
            )
            return success
        else:
            reason = f"Недостаточное улучшение ({comparison.improvement:.1f}% < {metric_threshold*100}%)"
            await self.reject_version(capability, candidate_version, reason)
            return False

    async def _execute_scenario(
        self,
        scenario: BenchmarkScenario,
        version: str,
        agent_executor=None
    ) -> Optional[ActualOutput]:
        """
        Выполнение сценария бенчмарка.

        ARGS:
        - scenario: сценарий бенчмарка
        - version: версия для тестирования
        - agent_executor: функция выполнения агента

        RETURNS:
        - ActualOutput: фактический вывод
        """
        if agent_executor:
            # Использование предоставленного executor
            result = await agent_executor(scenario.goal, version)
            return ActualOutput(
                content=result.get('content'),
                execution_time_ms=result.get('execution_time_ms', 0),
                tokens_used=result.get('tokens_used', 0)
            )
        else:
            # Mock выполнение (для тестов)
            await self.event_bus_logger.warning("Agent executor не предоставлен, используется mock")
            return ActualOutput(
                content="Mock response",
                execution_time_ms=100.0,
                tokens_used=50
            )

    async def _evaluate_result(
        self,
        scenario: BenchmarkScenario,
        actual_output: ActualOutput
    ) -> List[CriterionScore]:
        """
        Оценка результата бенчмарка.

        ARGS:
        - scenario: сценарий бенчмарка
        - actual_output: фактический вывод

        RETURNS:
        - List[CriterionScore]: оценки по критериям
        """
        scores = []

        # Оценка по каждому критерию сценария
        for criterion in scenario.criteria:
            result = await self.accuracy_evaluator.evaluate(
                scenario.expected_output,
                actual_output,
                criterion
            )

            score = CriterionScore(
                criterion=criterion,
                score=result.score,
                passed=result.passed,
                details=result.details
            )
            scores.append(score)

        # Если нет критериев, используем default
        if not scores and scenario.expected_output:
            # Простая оценка совпадения
            if actual_output and actual_output.content == scenario.expected_output.content:
                scores.append(CriterionScore(
                    criterion=EvaluationCriterion(
                        name='default',
                        evaluation_type=scenario.expected_output.criteria[0].evaluation_type if scenario.expected_output.criteria else None
                    ),
                    score=1.0,
                    passed=True
                ))

        return scores

    def _calculate_overall_score(self, scores: List[CriterionScore]) -> float:
        """
        Расчёт общей оценки.

        ARGS:
        - scores: оценки по критериям

        RETURNS:
        - float: общая оценка (0.0-1.0)
        """
        if not scores:
            return 0.0

        total_weight = sum(s.criterion.weight for s in scores)
        if total_weight == 0:
            return sum(s.score for s in scores) / len(scores)

        weighted_sum = sum(s.score * s.criterion.weight for s in scores)
        return weighted_sum / total_weight

    def _determine_success(
        self,
        scores: List[CriterionScore],
        overall_score: float,
        scenario: BenchmarkScenario
    ) -> bool:
        """
        Определение успешности бенчмарка.

        ARGS:
        - scores: оценки по критериям
        - overall_score: общая оценка
        - scenario: сценарий бенчмарка

        RETURNS:
        - bool: успешность
        """
        # Все критерии должны быть пройдены
        all_passed = all(s.passed for s in scores)

        # Или общая оценка выше порога
        threshold = 0.8  # Default threshold

        return all_passed or overall_score >= threshold

    def _aggregate_metrics(self, results: List[BenchmarkResult]) -> Dict[str, float]:
        """
        Агрегация метрик из результатов.

        ARGS:
        - results: список результатов бенчмарка

        RETURNS:
        - Dict[str, float]: агрегированные метрики
        """
        if not results:
            return {'accuracy': 0.0}

        total_runs = len(results)
        successful_runs = sum(1 for r in results if r.success)

        accuracy = successful_runs / total_runs if total_runs > 0 else 0.0

        avg_execution_time = sum(r.execution_time_ms for r in results) / total_runs
        avg_tokens = sum(r.tokens_used for r in results) / total_runs
        avg_score = sum(r.overall_score for r in results) / total_runs

        return {
            'accuracy': accuracy,
            'avg_execution_time_ms': avg_execution_time,
            'avg_tokens': avg_tokens,
            'avg_score': avg_score
        }

    def _check_statistical_significance(
        self,
        results_a: List[BenchmarkResult],
        results_b: List[BenchmarkResult]
    ) -> bool:
        """
        Проверка статистической значимости различий.

        Упрощённая проверка: достаточно ли разницы в accuracy.

        ARGS:
        - results_a: результаты версии A
        - results_b: результаты версии B

        RETURNS:
        - bool: статистически значимо ли различие
        """
        if len(results_a) < 3 or len(results_b) < 3:
            return False  # Недостаточно данных

        accuracy_a = sum(1 for r in results_a if r.success) / len(results_a)
        accuracy_b = sum(1 for r in results_b if r.success) / len(results_b)

        # Простая проверка: разница > 10%
        return abs(accuracy_b - accuracy_a) > 0.1

    async def _publish_benchmark_start(self, scenario: BenchmarkScenario, version: str) -> None:
        """Публикация события начала бенчмарка"""
        await self.event_bus.publish(
            EventType.BENCHMARK_STARTED,
            data={
                'scenario_id': scenario.id,
                'scenario_name': scenario.name,
                'version': version,
                'timestamp': datetime.now().isoformat()
            }
        )

    async def _publish_benchmark_complete(self, result: BenchmarkResult) -> None:
        """Публикация события завершения бенчмарка"""
        await self.event_bus.publish(
            EventType.BENCHMARK_COMPLETED,
            data={
                'scenario_id': result.scenario_id,
                'success': result.success,
                'overall_score': result.overall_score,
                'execution_time_ms': result.execution_time_ms,
                'tokens_used': result.tokens_used,
                'timestamp': result.timestamp.isoformat()
            }
        )

    async def _publish_benchmark_failed(self, scenario: BenchmarkScenario, version: str, error: str) -> None:
        """Публикация события ошибки бенчмарка"""
        await self.event_bus.publish(
            EventType.BENCHMARK_FAILED,
            data={
                'scenario_id': scenario.id,
                'version': version,
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
        )

    def set_registry_callback(self, callback) -> None:
        """
        Установка callback для обновления registry.

        ARGS:
        - callback: асинхронная функция(capability, from_version, to_version)
        """
        self._on_version_promoted = callback
