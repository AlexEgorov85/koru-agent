"""
Модели данных для системы метрик.

КОМПОНЕНТЫ:
- MetricType: типы метрик (GAUGE, COUNTER, HISTOGRAM)
- MetricRecord: запись отдельной метрики
- AggregatedMetrics: агрегированные метрики для бенчмарка
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import statistics


class MetricType(Enum):
    """
    Типы метрик в системе.

    TYPES:
    - GAUGE: метрика-значение (например, accuracy)
    - COUNTER: счётчик (например, количество выполнений)
    - HISTOGRAM: распределение (например, время выполнения)
    """
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"


@dataclass
class MetricRecord:
    """
    Запись отдельной метрики.

    ATTRIBUTES:
    - agent_id: идентификатор агента
    - capability: название способности
    - metric_type: тип метрики
    - name: имя метрики
    - value: значение метрики
    - timestamp: время записи
    - session_id: идентификатор сессии
    - correlation_id: идентификатор корреляции
    - version: версия промпта/контракта
    - tags: дополнительные теги
    """
    agent_id: str
    capability: str
    metric_type: MetricType
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    version: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'agent_id': self.agent_id,
            'capability': self.capability,
            'metric_type': self.metric_type.value,
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'correlation_id': self.correlation_id,
            'version': self.version,
            'tags': self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetricRecord':
        """Десериализация из словаря"""
        return cls(
            agent_id=data['agent_id'],
            capability=data['capability'],
            metric_type=MetricType(data['metric_type']),
            name=data['name'],
            value=data['value'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            session_id=data.get('session_id'),
            correlation_id=data.get('correlation_id'),
            version=data.get('version'),
            tags=data.get('tags', {})
        )


@dataclass
class AggregatedMetrics:
    """
    Агрегированные метрики для бенчмарка.

    ATTRIBUTES:
    - capability: название способности
    - version: версия промпта/контракта
    - total_runs: общее количество запусков
    - success_count: количество успешных выполнений
    - failure_count: количество неудачных выполнений
    - accuracy: точность (success_count / total_runs)
    - avg_execution_time_ms: среднее время выполнения
    - min_execution_time_ms: минимальное время выполнения
    - max_execution_time_ms: максимальное время выполнения
    - std_execution_time_ms: стандартное отклонение времени выполнения
    - total_tokens: общее количество использованных токенов
    - avg_tokens: среднее количество токенов на запуск
    - time_range: временной диапазон агрегации
    - custom_metrics: пользовательские метрики
    """
    capability: str
    version: str
    total_runs: int = 0
    success_count: int = 0
    failure_count: int = 0
    accuracy: float = 0.0
    avg_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    std_execution_time_ms: float = 0.0
    total_tokens: int = 0
    avg_tokens: float = 0.0
    time_range: tuple = field(default_factory=lambda: (None, None))
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_records(cls, capability: str, version: str, records: List[MetricRecord]) -> 'AggregatedMetrics':
        """
        Создание агрегированных метрик из списка записей.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта
        - records: список записей метрик

        RETURNS:
        - AggregatedMetrics: агрегированные метрики
        """
        if not records:
            return cls(capability=capability, version=version)

        # Извлечение значений метрик
        execution_times = []
        tokens_list = []
        success_count = 0
        failure_count = 0
        custom_metrics_values: Dict[str, List[float]] = {}

        for record in records:
            # Подсчёт успехов/неудач
            if record.name == 'success':
                if record.value > 0:
                    success_count += 1
                else:
                    failure_count += 1

            # Время выполнения
            if record.name == 'execution_time_ms':
                execution_times.append(record.value)

            # Токены
            if record.name == 'tokens_used':
                tokens_list.append(record.value)

            # Пользовательские метрики (GAUGE)
            if record.metric_type == MetricType.GAUGE and record.name not in ['success', 'execution_time_ms', 'tokens_used', 'accuracy']:
                if record.name not in custom_metrics_values:
                    custom_metrics_values[record.name] = []
                custom_metrics_values[record.name].append(record.value)

        total_runs = success_count + failure_count
        accuracy = success_count / total_runs if total_runs > 0 else 0.0

        # Статистика времени выполнения
        avg_execution_time = statistics.mean(execution_times) if execution_times else 0.0
        min_execution_time = min(execution_times) if execution_times else 0.0
        max_execution_time = max(execution_times) if execution_times else 0.0
        std_execution_time = statistics.stdev(execution_times) if len(execution_times) > 1 else 0.0

        # Статистика токенов
        total_tokens = sum(tokens_list) if tokens_list else 0
        avg_tokens = statistics.mean(tokens_list) if tokens_list else 0.0

        # Временной диапазон
        timestamps = [r.timestamp for r in records]
        time_range = (min(timestamps), max(timestamps)) if timestamps else (None, None)

        # Пользовательские метрики (среднее значение)
        custom_metrics = {
            name: statistics.mean(values)
            for name, values in custom_metrics_values.items()
            if values
        }

        return cls(
            capability=capability,
            version=version,
            total_runs=total_runs,
            success_count=success_count,
            failure_count=failure_count,
            accuracy=accuracy,
            avg_execution_time_ms=avg_execution_time,
            min_execution_time_ms=min_execution_time,
            max_execution_time_ms=max_execution_time,
            std_execution_time_ms=std_execution_time,
            total_tokens=total_tokens,
            avg_tokens=avg_tokens,
            time_range=time_range,
            custom_metrics=custom_metrics
        )

    def is_better_than(self, other: 'AggregatedMetrics', metric: str = 'accuracy') -> bool:
        """
        Сравнение с другими метриками по указанному параметру.

        ARGS:
        - other: другие агрегированные метрики
        - metric: имя метрики для сравнения

        RETURNS:
        - bool: True если текущие метрики лучше
        """
        if metric == 'accuracy':
            return self.accuracy > other.accuracy
        elif metric == 'avg_execution_time_ms':
            # Меньше время = лучше
            return self.avg_execution_time_ms < other.avg_execution_time_ms
        elif metric == 'avg_tokens':
            # Меньше токенов = лучше
            return self.avg_tokens < other.avg_tokens
        elif metric in self.custom_metrics:
            return self.custom_metrics[metric] > other.custom_metrics.get(metric, 0.0)
        else:
            # По умолчанию сравниваем accuracy
            return self.accuracy > other.accuracy

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'capability': self.capability,
            'version': self.version,
            'total_runs': self.total_runs,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'accuracy': self.accuracy,
            'avg_execution_time_ms': self.avg_execution_time_ms,
            'min_execution_time_ms': self.min_execution_time_ms,
            'max_execution_time_ms': self.max_execution_time_ms,
            'std_execution_time_ms': self.std_execution_time_ms,
            'total_tokens': self.total_tokens,
            'avg_tokens': self.avg_tokens,
            'time_range': [
                self.time_range[0].isoformat() if self.time_range[0] else None,
                self.time_range[1].isoformat() if self.time_range[1] else None
            ],
            'custom_metrics': self.custom_metrics
        }
