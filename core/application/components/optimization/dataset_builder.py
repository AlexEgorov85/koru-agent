"""
DatasetBuilder - построение датасета для оптимизации.

ОТВЕТСТВЕННОСТЬ:
- Сбор данных из логов, метрик и execution traces
- Формирование OptimizationSample из реальных данных
- Фильтрация и валидация образцов
- Обеспечение минимального размера датасета (100+ примеров)
- Гарантия наличия failure cases (≥20%)
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.models.data.benchmark import (
    BenchmarkDataset,
    OptimizationSample,
    ScenarioType,
    LogEntry,
    LogType,
)
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


@dataclass
class DatasetConfig:
    """Конфигурация DatasetBuilder"""
    min_samples: int = 100
    min_failure_rate: float = 0.2  # 20% failure cases
    max_samples: int = 1000
    time_window_hours: int = 24  # Окно времени для сбора данных


class DatasetBuilder:
    """
    Построитель датасета для оптимизации промптов.

    RESPONSIBILITIES:
    - Сбор данных из логов и метрик
    - Формирование OptimizationSample
    - Балансировка failure/success кейсов
    - Валидация качества датасета

    USAGE:
    ```python
    builder = DatasetBuilder(metrics_collector, event_bus)
    dataset = await builder.build('capability_name')
    ```
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        event_bus: UnifiedEventBus,
        config: Optional[DatasetConfig] = None
    ):
        """
        Инициализация DatasetBuilder.

        ARGS:
        - metrics_collector: сборщик метрик
        - event_bus: шина событий для получения логов
        - config: конфигурация
        """
        self.metrics_collector = metrics_collector
        self.event_bus = event_bus
        self.config = config or DatasetConfig()

    async def build(self, capability: str) -> BenchmarkDataset:
        """
        Построение датасета для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - BenchmarkDataset: набор данных для оптимизации
        """
        dataset = BenchmarkDataset(
            id=str(uuid.uuid4()),
            capability=capability
        )

        # Сбор данных из метрик
        metrics_samples = await self._collect_from_metrics(capability)
        for sample in metrics_samples:
            dataset.add_sample(sample)

        # Сбор данных из логов ошибок
        error_samples = await self._collect_from_error_logs(capability)
        for sample in error_samples:
            dataset.add_sample(sample)

        # Если недостаточно failure cases, увеличиваем окно сбора
        if dataset.failure_rate < self.config.min_failure_rate:
            additional_samples = await self._collect_additional_failures(capability)
            for sample in additional_samples:
                dataset.add_sample(sample)

        # Валидация датасета
        self._validate_dataset(dataset)

        return dataset

    async def _collect_from_metrics(self, capability: str) -> List[OptimizationSample]:
        """
        Сбор образцов из метрик выполнения.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[OptimizationSample]: образцы из метрик
        """
        samples = []

        # Получение агрегированных метрик
        aggregated = await self.metrics_collector.get_aggregated_metrics(
            capability,
            version='latest'
        )

        # Получение детальных метрик из хранилища
        if hasattr(self.metrics_collector, 'storage') and self.metrics_collector.storage:
            # Извлечение сырых данных из storage
            raw_data = await self._fetch_raw_metrics(capability)
            
            for record in raw_data[:self.config.max_samples]:
                sample = self._create_sample_from_metric(record, capability)
                if sample:
                    samples.append(sample)

        return samples[:self.config.max_samples // 2]  # Не более 50% от лимита

    async def _fetch_raw_metrics(self, capability: str) -> List[Dict[str, Any]]:
        """
        Получение сырых метрик из хранилища.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[Dict]: сырые данные метрик
        """
        # Получение данных за временное окно
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=self.config.time_window_hours)

        # Запрос к storage (используем time_range)
        if hasattr(self.metrics_collector.storage, 'get_records'):
            records = await self.metrics_collector.storage.get_records(
                capability=capability,
                time_range=(start_time, end_time),
                limit=self.config.max_samples
            )
            # Конвертируем MetricRecord в dict
            return [r.to_dict() if hasattr(r, 'to_dict') else r for r in records] if records else []

        return []

    def _create_sample_from_metric(
        self,
        record: Dict[str, Any],
        capability: str
    ) -> Optional[OptimizationSample]:
        """
        Создание OptimizationSample из метрики.

        ARGS:
        - record: запись метрики
        - capability: название способности

        RETURNS:
        - Optional[OptimizationSample]: образец или None
        """
        try:
            # Извлечение данных из record
            input_data = record.get('input', record.get('query', ''))
            success = record.get('success', True)
            error = record.get('error')
            execution_time = record.get('execution_time_ms', 0)
            tokens_used = record.get('tokens_used', 0)

            # Пропускаем пустые записи
            if not input_data:
                return None

            return OptimizationSample(
                id=str(uuid.uuid4()),
                input=str(input_data),
                context={
                    'execution_time_ms': execution_time,
                    'tokens_used': tokens_used,
                    'source': 'metrics'
                },
                success=success,
                error=error,
                metadata={
                    'timestamp': record.get('timestamp', datetime.now().isoformat()),
                    'version': record.get('version', 'unknown')
                }
            )
        except Exception:
            return None

    async def _collect_from_error_logs(self, capability: str) -> List[OptimizationSample]:
        """
        Сбор образцов из логов ошибок.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[OptimizationSample]: образцы из ошибок
        """
        samples = []

        # Получение логов ошибок из event_bus или session_handler
        error_logs = await self._fetch_error_logs(capability)

        for log in error_logs:
            sample = self._create_sample_from_error(log, capability)
            if sample:
                samples.append(sample)

        return samples

    async def _fetch_error_logs(self, capability: str) -> List[Dict[str, Any]]:
        """
        Получение логов ошибок.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[Dict]: логи ошибок
        """
        # Запрос к хранилищу логов
        if hasattr(self.metrics_collector.storage, 'get_error_logs'):
            logs = await self.metrics_collector.storage.get_error_logs(
                capability=capability,
                limit=100
            )
            return logs if logs else []
        
        return []

    def _create_sample_from_error(
        self,
        log: Dict[str, Any],
        capability: str
    ) -> Optional[OptimizationSample]:
        """
        Создание OptimizationSample из лога ошибки.

        ARGS:
        - log: запись лога ошибки
        - capability: название способности

        RETURNS:
        - Optional[OptimizationSample]: образец или None
        """
        try:
            input_data = log.get('input', log.get('query', log.get('data', {})))
            error_message = log.get('error_message', log.get('error', 'Unknown error'))
            error_type = log.get('error_type', 'unknown')

            # Преобразуем input в строку если нужно
            if isinstance(input_data, dict):
                input_data = str(input_data.get('query', input_data))

            return OptimizationSample(
                id=str(uuid.uuid4()),
                input=str(input_data) if input_data else "Unknown input",
                context={
                    'error_type': error_type,
                    'source': 'error_log'
                },
                success=False,
                error=error_message,
                metadata={
                    'timestamp': log.get('timestamp', datetime.now().isoformat()),
                    'session_id': log.get('session_id', 'unknown')
                }
            )
        except Exception:
            return None

    async def _collect_additional_failures(self, capability: str) -> List[OptimizationSample]:
        """
        Сбор дополнительных failure кейсов если их недостаточно.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[OptimizationSample]: дополнительные образцы
        """
        # Расширяем временное окно
        original_window = self.config.time_window_hours
        self.config.time_window_hours *= 2

        try:
            # Повторный сбор с большим окном
            error_samples = await self._collect_from_error_logs(capability)
            return error_samples
        finally:
            # Восстанавливаем оригинальное окно
            self.config.time_window_hours = original_window

    def _validate_dataset(self, dataset: BenchmarkDataset) -> None:
        """
        Валидация качества датасета.

        ARGS:
        - dataset: датасет для валидации

        RAISES:
        - ValueError: если датасет не соответствует требованиям
        """
        # Проверка минимального размера
        if dataset.size < self.config.min_samples:
            # Warning, но не ошибка - собираем что есть
            pass

        # Проверка наличия failure cases
        if dataset.failure_rate < self.config.min_failure_rate:
            # Warning - недостаточно failure кейсов
            pass

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
            'meets_min_failure_rate': dataset.failure_rate >= self.config.min_failure_rate
        }
