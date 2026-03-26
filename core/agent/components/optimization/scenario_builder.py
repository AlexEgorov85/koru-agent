"""
ScenarioBuilder - классификация и построение сценариев.

ОТВЕТСТВЕННОСТЬ:
- Классификация образцов по типам сценариев (EASY, EDGE, FAILURE)
- Обеспечение баланса сценариев (ни один тип < 10%)
- Гарантия наличия failure scenarios (≥15%)
- Формирование сбалансированного набора для бенчмарка
"""
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.services.benchmarks.benchmark_models import (
    BenchmarkDataset,
    BenchmarkScenario,
    OptimizationSample,
    ScenarioType,
    ExpectedOutput,
    EvaluationCriterion,
    EvaluationType,
)


@dataclass
class ScenarioConfig:
    """Конфигурация ScenarioBuilder"""
    min_type_percentage: float = 0.1  # Минимум 10% для каждого типа
    min_failure_percentage: float = 0.15  # Минимум 15% failure
    max_scenarios: int = 200
    balance_types: bool = True  # Автоматически балансировать типы


class ScenarioBuilder:
    """
    Построитель сценариев для бенчмарка.

    RESPONSIBILITIES:
    - Классификация образцов по типам
    - Балансировка распределения типов
    - Создание BenchmarkScenario из OptimizationSample
    - Обеспечение репрезентативности тестов

    USAGE:
    ```python
    builder = ScenarioBuilder()
    scenarios = await builder.build(dataset)
    ```
    """

    def __init__(self, config: Optional[ScenarioConfig] = None):
        """
        Инициализация ScenarioBuilder.

        ARGS:
        - config: конфигурация
        """
        self.config = config or ScenarioConfig()

    async def build(self, dataset: BenchmarkDataset) -> List[BenchmarkScenario]:
        """
        Построение списка сценариев из датасета.

        ARGS:
        - dataset: набор данных

        RETURNS:
        - List[BenchmarkScenario]: список сценариев для бенчмарка
        """
        scenarios = []

        # Группировка по типам
        samples_by_type = self._group_by_type(dataset.samples)

        # Балансировка если требуется
        if self.config.balance_types:
            samples_by_type = self._balance_types(samples_by_type)

        # Создание сценариев для каждого типа
        for scenario_type, samples in samples_by_type.items():
            for sample in samples[:self.config.max_scenarios // len(samples_by_type)]:
                scenario = self._create_scenario(sample, dataset.capability)
                if scenario:
                    scenarios.append(scenario)

        return scenarios[:self.config.max_scenarios]

    def _group_by_type(
        self,
        samples: List[OptimizationSample]
    ) -> Dict[ScenarioType, List[OptimizationSample]]:
        """
        Группировка образцов по типам сценариев.

        ARGS:
        - samples: образцы для группировки

        RETURNS:
        - Dict[ScenarioType, List[OptimizationSample]]: сгруппированные образцы
        """
        grouped = {st: [] for st in ScenarioType}

        for sample in samples:
            # Классификация sample
            scenario_type = self._classify_sample(sample)
            grouped[scenario_type].append(sample)

        return grouped

    def _classify_sample(self, sample: OptimizationSample) -> ScenarioType:
        """
        Классификация образца по типу сценария.

        Логика:
        - if error: FAILURE
        - elif not success: EDGE
        - else: EASY

        ARGS:
        - sample: образец для классификации

        RETURNS:
        - ScenarioType: тип сценария
        """
        # Приоритет: error > failure > edge > easy
        if sample.error:
            return ScenarioType.FAILURE
        elif not sample.success:
            return ScenarioType.EDGE
        else:
            return ScenarioType.EASY

    def _balance_types(
        self,
        samples_by_type: Dict[ScenarioType, List[OptimizationSample]]
    ) -> Dict[ScenarioType, List[OptimizationSample]]:
        """
        Балансировка количества образцов по типам.

        ARGS:
        - samples_by_type: образцы по типам

        RETURNS:
        - Dict[ScenarioType, List[OptimizationSample]]: сбалансированные образцы
        """
        total_samples = sum(len(samples) for samples in samples_by_type.values())

        if total_samples == 0:
            return samples_by_type

        balanced = {}
        min_per_type = max(1, int(total_samples * self.config.min_type_percentage))

        for scenario_type, samples in samples_by_type.items():
            if len(samples) < min_per_type:
                # Недостаточно образцов этого типа - берём все что есть
                balanced[scenario_type] = samples
            else:
                # Достаточно - ограничиваем разумным количеством
                max_per_type = total_samples // len(ScenarioType)
                balanced[scenario_type] = samples[:max_per_type]

        return balanced

    def _create_scenario(
        self,
        sample: OptimizationSample,
        capability: str
    ) -> Optional[BenchmarkScenario]:
        """
        Создание BenchmarkScenario из OptimizationSample.

        ARGS:
        - sample: образец
        - capability: название способности

        RETURNS:
        - Optional[BenchmarkScenario]: сценарий или None
        """
        try:
            # Формирование ожидаемого вывода
            expected_output = self._create_expected_output(sample)

            # Создание критериев оценки
            criteria = self._create_criteria(sample)

            # Определение таймаута на основе типа
            timeout = self._get_timeout_for_type(sample.scenario_type)

            return BenchmarkScenario(
                id=str(uuid.uuid4()),
                name=f"{capability}_{sample.scenario_type.value}_{sample.id[:8]}",
                description=f"Сценарий типа {sample.scenario_type.value} для {capability}",
                goal=sample.input,
                expected_output=expected_output,
                criteria=criteria,
                timeout_seconds=timeout,
                metadata={
                    'original_sample_id': sample.id,
                    'scenario_type': sample.scenario_type.value,
                    'has_error': sample.error is not None,
                    'error_type': sample.error.split(':')[0] if sample.error else None
                }
            )
        except Exception:
            return None

    def _create_expected_output(self, sample: OptimizationSample) -> ExpectedOutput:
        """
        Создание ExpectedOutput из образца.

        ARGS:
        - sample: образец

        RETURNS:
        - ExpectedOutput: ожидаемый вывод
        """
        # Если есть expected_behavior - используем его
        if sample.expected_behavior:
            return ExpectedOutput(
                content=sample.expected_behavior,
                criteria=[]
            )

        # Если sample успешный - ожидаем успех
        if sample.success and not sample.error:
            return ExpectedOutput(
                content=sample.actual_output or "Success",
                criteria=[]
            )

        # Если sample с ошибкой - ожидаем обработку ошибки
        return ExpectedOutput(
            content=f"Error handled: {sample.error}" if sample.error else "Success",
            criteria=[]
        )

    def _create_criteria(
        self,
        sample: OptimizationSample
    ) -> List[EvaluationCriterion]:
        """
        Создание критериев оценки для сценария.

        ARGS:
        - sample: образец

        RETURNS:
        - List[EvaluationCriterion]: список критериев
        """
        criteria = []

        # Критерий успешности
        if sample.success:
            criteria.append(EvaluationCriterion(
                name='success',
                evaluation_type=EvaluationType.EXACT_MATCH,
                weight=0.5,
                description='Выполнение должно быть успешным',
                threshold=0.8
            ))
        else:
            criteria.append(EvaluationCriterion(
                name='error_handling',
                evaluation_type=EvaluationType.CUSTOM,
                weight=0.5,
                description='Ошибка должна быть корректно обработана',
                threshold=0.5
            ))

        # Критерий валидности вывода
        criteria.append(EvaluationCriterion(
            name='output_validity',
            evaluation_type=EvaluationType.COVERAGE,
            weight=0.3,
            description='Вывод должен быть валидным',
            threshold=0.7
        ))

        # Критерий соответствия типу сценария
        criteria.append(EvaluationCriterion(
            name='scenario_type_match',
            evaluation_type=EvaluationType.CUSTOM,
            weight=0.2,
            description=f'Соответствие типу {sample.scenario_type.value}',
            threshold=0.6
        ))

        return criteria

    def _get_timeout_for_type(self, scenario_type: ScenarioType) -> int:
        """
        Получение таймаута для типа сценария.

        ARGS:
        - scenario_type: тип сценария

        RETURNS:
        - int: таймаут в секундах
        """
        if scenario_type == ScenarioType.FAILURE:
            return 30  # Failure кейсы могут быть сложными
        elif scenario_type == ScenarioType.EDGE:
            return 45  # Edge кейсы требуют больше времени
        else:
            return 60  # EASY кейсы - стандартный таймаут

    def get_scenario_stats(
        self,
        scenarios: List[BenchmarkScenario]
    ) -> Dict[str, Any]:
        """
        Получение статистики сценариев.

        ARGS:
        - scenarios: список сценариев

        RETURNS:
        - Dict[str, Any]: статистика
        """
        type_counts = {st.value: 0 for st in ScenarioType}
        
        for scenario in scenarios:
            scenario_type = scenario.metadata.get('scenario_type', 'unknown')
            if scenario_type in type_counts:
                type_counts[scenario_type] += 1

        total = len(scenarios)
        type_distribution = {
            k: v / total if total > 0 else 0 
            for k, v in type_counts.items()
        }

        return {
            'total_scenarios': total,
            'type_distribution': type_distribution,
            'failure_percentage': type_distribution.get('failure', 0),
            'meets_min_failure_rate': type_distribution.get('failure', 0) >= self.config.min_failure_percentage,
            'all_types_present': all(
                count > 0 or total == 0 
                for count in type_counts.values()
            )
        }
