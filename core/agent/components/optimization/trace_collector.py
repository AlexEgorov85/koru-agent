"""
TraceCollector — сбор execution traces.

КОМПОНЕНТЫ:
- TraceCollector: сбор и реконструкция traces

FEATURES:
- Сбор traces для capability
- Фильтрация по успешности/неуспешности
- Балансировка успешных/неуспешных traces
- Конвертация в OptimizationSample
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.models.data.execution_trace import ExecutionTrace, StepTrace
from core.components.benchmarks.benchmark_models import OptimizationSample, ScenarioType, BenchmarkDataset
from .trace_handler import TraceHandler


@dataclass
class TraceCollectionConfig:
    """Конфигурация сбора traces"""
    min_samples: int = 50
    max_samples: int = 200
    min_failure_rate: float = 0.2  # 20% failure cases
    include_success: bool = True
    include_failure: bool = True


class TraceCollector:
    """
    Сборщик execution traces.

    RESPONSIBILITIES:
    - Сбор traces для capability
    - Балансировка успешных/неуспешных traces
    - Конвертация в OptimizationSample
    - Построение BenchmarkDataset

    USAGE:
    ```python
    collector = TraceCollector(trace_handler)
    traces = await collector.collect_traces('planning.create_plan')
    dataset = await collector.build_dataset('planning.create_plan')
    ```
    """

    def __init__(
        self,
        trace_handler: TraceHandler,
        config: Optional[TraceCollectionConfig] = None
    ):
        """
        Инициализация TraceCollector.

        ARGS:
        - trace_handler: обработчик traces
        - config: конфигурация
        """
        self.trace_handler = trace_handler
        self.config = config or TraceCollectionConfig()

    async def collect_traces(
        self,
        capability: str,
        min_samples: Optional[int] = None,
        include_success: Optional[bool] = None,
        include_failure: Optional[bool] = None
    ) -> List[ExecutionTrace]:
        """
        Сбор traces для capability.

        ARGS:
        - capability: название способности
        - min_samples: минимум образцов
        - include_success: включать успешные
        - include_failure: включать неуспешные

        RETURNS:
        - List[ExecutionTrace]: список traces
        """
        min_samples = min_samples or self.config.min_samples
        include_success = include_success if include_success is not None else self.config.include_success
        include_failure = include_failure if include_failure is not None else self.config.include_failure

        traces = []

        # Сбор успешных traces
        if include_success:
            success_traces = await self.trace_handler.get_successful_traces(
                capability,
                limit=min_samples
            )
            traces.extend(success_traces)

        # Сбор неуспешных traces
        if include_failure:
            failure_traces = await self.trace_handler.get_failed_traces(
                capability,
                limit=min_samples
            )
            traces.extend(failure_traces)

        # Балансировка
        traces = self._balance_traces(traces)

        # Ограничение по максимуму
        max_samples = self.config.max_samples
        return traces[:max_samples]

    async def build_dataset(
        self,
        capability: str
    ) -> BenchmarkDataset:
        """
        Построение BenchmarkDataset из traces.

        ARGS:
        - capability: название способности

        RETURNS:
        - BenchmarkDataset: набор данных
        """
        import uuid

        # Сбор traces
        traces = await self.collect_traces(capability)

        # Конвертация в samples
        samples = []
        for trace in traces:
            sample = self._trace_to_sample(trace)
            samples.append(sample)

        # Создание датасета
        dataset = BenchmarkDataset(
            id=str(uuid.uuid4()),
            capability=capability,
            samples=samples
        )

        return dataset

    def _balance_traces(
        self,
        traces: List[ExecutionTrace]
    ) -> List[ExecutionTrace]:
        """
        Балансировка успешных/неуспешных traces.

        Цель: обеспечить min_failure_rate

        ARGS:
        - traces: список traces

        RETURNS:
        - List[ExecutionTrace]: сбалансированный список
        """
        if not traces:
            return []

        # Разделение на успешные/неуспешные
        success_traces = [t for t in traces if t.success]
        failure_traces = [t for t in traces if not t.success]

        total_needed = len(traces)
        min_failures_needed = int(total_needed * self.config.min_failure_rate)

        # Если недостаточно failure traces
        if len(failure_traces) < min_failures_needed:
            # Берём все что есть
            balanced = failure_traces + success_traces[:(total_needed - len(failure_traces))]
        else:
            # Балансируем
            balanced = failure_traces[:min_failures_needed] + success_traces[:(total_needed - min_failures_needed)]

        return balanced

    def _trace_to_sample(self, trace: ExecutionTrace) -> OptimizationSample:
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
            'error_types': list(trace.get_errors_by_type().keys())
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

    def get_collection_stats(
        self,
        traces: List[ExecutionTrace]
    ) -> Dict[str, Any]:
        """
        Получение статистики сбора.

        ARGS:
        - traces: список traces

        RETURNS:
        - Dict[str, Any]: статистика
        """
        if not traces:
            return {
                'total_traces': 0,
                'success_count': 0,
                'failure_count': 0,
                'failure_rate': 0.0
            }

        success_count = sum(1 for t in traces if t.success)
        failure_count = len(traces) - success_count

        return {
            'total_traces': len(traces),
            'success_count': success_count,
            'failure_count': failure_count,
            'failure_rate': failure_count / len(traces) if traces else 0.0,
            'avg_steps': sum(t.step_count for t in traces) / len(traces),
            'avg_time_ms': sum(t.total_time_ms for t in traces) / len(traces),
            'avg_tokens': sum(t.total_tokens for t in traces) / len(traces),
            'meets_min_samples': len(traces) >= self.config.min_samples,
            'meets_min_failure_rate': (failure_count / len(traces)) >= self.config.min_failure_rate if traces else False
        }

    async def collect_traces_with_stats(
        self,
        capability: str
    ) -> tuple:
        """
        Сбор traces с статистикой.

        ARGS:
        - capability: название способности

        RETURNS:
        - tuple: (traces, stats)
        """
        traces = await self.collect_traces(capability)
        stats = self.get_collection_stats(traces)
        return traces, stats
