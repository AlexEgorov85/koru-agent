"""
DatasetBuilder — построение датасета из execution traces.

ОТВЕТСТВЕННОСТЬ:
- Сбор данных из execution traces (а не только метрик)
- Формирование OptimizationSample с полным контекстом
- Балансировка успешных/неуспешных кейсов
- Интеграция с TraceCollector
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.benchmarks.benchmark_models import (
    BenchmarkDataset,
    OptimizationSample,
    ScenarioType,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus

from .trace_collector import TraceCollector, TraceCollectionConfig
from .trace_handler import TraceHandler


@dataclass
class DatasetBuilderConfig:
    """Конфигурация DatasetBuilder"""
    min_samples: int = 50
    min_failure_rate: float = 0.2  # 20% failure cases
    max_samples: int = 500
    use_traces: bool = True  # Использовать traces вместо метрик


class DatasetBuilder:
    """
    Построитель датасета для оптимизации промптов.

    В ОТЛИЧИЕ ОТ СТАРОЙ ВЕРСИИ:
    - Использует execution traces вместо агрегированных метрик
    - Извлекает полный контекст выполнения
    - Сохраняет связи между шагами

    RESPONSIBILITIES:
    - Сбор traces через TraceCollector
    - Конвертация traces в OptimizationSample
    - Балансировка failure/success кейсов
    - Валидация качества датасета

    USAGE:
    ```python
    trace_handler = TraceHandler(session_handler)
    trace_collector = TraceCollector(trace_handler)
    builder = DatasetBuilder.from_trace_collector(trace_collector)
    dataset = await builder.build('capability_name')
    ```
    """

    def __init__(
        self,
        trace_collector: TraceCollector,
        event_bus: UnifiedEventBus,
        config: Optional[DatasetBuilderConfig] = None
    ):
        """
        Инициализация DatasetBuilder.

        ARGS:
        - trace_collector: сборщик traces
        - event_bus: шина событий
        - config: конфигурация
        """
        self.trace_collector = trace_collector
        self.event_bus = event_bus
        self.config = config or DatasetBuilderConfig()

    @classmethod
    def from_trace_collector(
        cls,
        trace_collector: TraceCollector,
        event_bus: Optional[UnifiedEventBus] = None
    ) -> 'DatasetBuilder':
        """
        Создание DatasetBuilder из TraceCollector.

        ARGS:
        - trace_collector: сборщик traces
        - event_bus: шина событий (опционально)

        RETURNS:
        - DatasetBuilder: новый экземпляр
        """
        # Создаём mock event_bus если не предоставлен
        if event_bus is None:
            from unittest.mock import AsyncMock
            event_bus = AsyncMock()

        return cls(
            trace_collector=trace_collector,
            event_bus=event_bus
        )

    async def build(self, capability: str) -> BenchmarkDataset:
        """
        Построение датасета для capability из traces.

        ARGS:
        - capability: название способности

        RETURNS:
        - BenchmarkDataset: набор данных для оптимизации
        """
        dataset = BenchmarkDataset(
            id=str(uuid.uuid4()),
            capability=capability
        )

        # Сбор traces
        traces = await self.trace_collector.collect_traces(capability)

        # Конвертация в samples
        for trace in traces:
            sample = self._trace_to_sample(trace)
            dataset.add_sample(sample)

        # Валидация датасета
        self._validate_dataset(dataset)

        return dataset

    def _trace_to_sample(self, trace) -> OptimizationSample:
        """
        Конвертация ExecutionTrace в OptimizationSample.

        ARGS:
        - trace: execution trace

        RETURNS:
        - OptimizationSample: образец для оптимизации
        """
        # Извлечение ключевой информации
        input_text = trace.goal

        # Контекст из шагов
        context = {
            'steps': trace.step_count,
            'total_time_ms': trace.total_time_ms,
            'total_tokens': trace.total_tokens,
            'llm_calls': trace.llm_call_count,
            'capabilities_used': trace.get_capabilities_used(),
            'error_types': list(trace.get_errors_by_type().keys()),
            'step_details': [self._step_to_dict(step) for step in trace.steps]
        }

        # Ожидаемое поведение (можно извлечь из контрактов)
        expected_behavior = None  # TODO: извлечь из output контракта

        # Фактический вывод
        actual_output = trace.final_answer

        # Успешность
        success = trace.success

        # Ошибка
        error = trace.error

        # Метаданные
        metadata = {
            'session_id': trace.session_id,
            'agent_id': trace.agent_id,
            'started_at': trace.started_at.isoformat(),
            'completed_at': trace.completed_at.isoformat() if trace.completed_at else None,
            'trace': trace.to_dict()  # Полный trace для детального анализа
        }

        return OptimizationSample(
            id=trace.session_id,
            input=input_text,
            context=context,
            expected_behavior=expected_behavior,
            actual_output=actual_output,
            success=success,
            error=error,
            metadata=metadata
        )

    def _step_to_dict(self, step) -> Dict[str, Any]:
        """Конвертация шага в словарь"""
        return {
            'step_number': step.step_number,
            'capability': step.capability,
            'goal': step.goal,
            'success': step.success,
            'time_ms': step.time_ms,
            'tokens_used': step.tokens_used,
            'has_llm_request': step.llm_request is not None,
            'has_llm_response': step.llm_response is not None,
            'has_action': step.action is not None,
            'error_count': len(step.errors)
        }

    def _validate_dataset(self, dataset: BenchmarkDataset) -> None:
        """
        Валидация качества датасета.

        ARGS:
        - dataset: датасет для валидации
        """
        stats = self.get_dataset_stats(dataset)

        # Warning если недостаточно образцов
        if not stats['meets_min_samples']:
            pass  # Можно добавить логирование

        # Warning если недостаточно failure cases
        if not stats['meets_min_failure_rate']:
            pass  # Можно добавить логирование

    def get_dataset_stats(self, dataset: BenchmarkDataset) -> Dict[str, Any]:
        """
        Получение статистики датасета.

        ARGS:
        - dataset: датасет

        RETURNS:
        - Dict[str, Any]: статистика
        """
        type_distribution = dataset.get_type_distribution()

        return {
            'total_samples': dataset.size,
            'failure_count': dataset.failure_count,
            'failure_rate': dataset.failure_rate,
            'type_distribution': type_distribution,
            'meets_min_samples': dataset.size >= self.config.min_samples,
            'meets_min_failure_rate': dataset.failure_rate >= self.config.min_failure_rate,
            'avg_steps': self._calculate_avg_steps(dataset),
            'avg_time_ms': self._calculate_avg_time(dataset)
        }

    def _calculate_avg_steps(self, dataset: BenchmarkDataset) -> float:
        """Расчёт среднего количества шагов"""
        if not dataset.samples:
            return 0.0

        total_steps = sum(
            s.context.get('steps', 1) for s in dataset.samples
        )
        return total_steps / len(dataset.samples)

    def _calculate_avg_time(self, dataset: BenchmarkDataset) -> float:
        """Расчёт среднего времени выполнения"""
        if not dataset.samples:
            return 0.0

        total_time = sum(
            s.context.get('total_time_ms', 0) for s in dataset.samples
        )
        return total_time / len(dataset.samples)

    async def build_with_stats(self, capability: str) -> tuple:
        """
        Построение датасета со статистикой.

        ARGS:
        - capability: название способности

        RETURNS:
        - tuple: (dataset, stats)
        """
        dataset = await self.build(capability)
        stats = self.get_dataset_stats(dataset)
        return dataset, stats
