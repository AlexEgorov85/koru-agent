"""
Тонкая обёртка для унифицированной публикации метрик.

ЦЕЛЬ: Предоставить единый, типизированный API для публикации метрик,
используя существующие компоненты без излишней сложности.

ИСПОЛЬЗОВАНИЕ:
```python
# Инициализация
publisher = MetricsPublisher(storage, event_bus)

# Публикация метрик
await publisher.gauge("accuracy", 0.95, capability="sql_generation")
await publisher.counter("execution_count", capability="data_analysis")
await publisher.histogram("execution_time_ms", 150.5, capability="sql_generation")
```

ИНТЕГРАЦИЯ:
- Использует IMetricsStorage для сохранения метрик
- Опционально публикует события в UnifiedEventBus
- Совместим с существующими моделями MetricRecord и MetricType
"""

from datetime import datetime
from typing import Dict, Optional, Any, Union
from core.models.data.metrics import MetricRecord, MetricType
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


class MetricsPublisher:
    """
    Тонкая обёртка для унифицированной публикации метрик.
    
    ОСНОВНЫЕ ФУНКЦИИ:
    - Единый API для всех типов метрик
    - Типизированные параметры с валидацией
    - Интеграция с существующими компонентами
    - Опциональная публикация в EventBus
    """
    
    def __init__(
        self,
        storage: IMetricsStorage,
        event_bus: Optional[UnifiedEventBus] = None
    ):
        """
        Инициализация публикатора метрик.
        
        ARGS:
        - storage: хранилище метрик (обязательно)
        - event_bus: шина событий (опционально)
        """
        self.storage = storage
        self.event_bus = event_bus
    
    async def gauge(
        self,
        name: str,
        value: float,
        agent_id: str = "unknown",
        capability: str = "",
        tags: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        version: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        publish_event: bool = True
    ) -> MetricRecord:
        """
        Публикация метрики типа GAUGE.
        
        GAUGE метрики представляют текущее значение (accuracy, temperature, etc).
        
        ARGS:
        - name: имя метрики
        - value: значение метрики
        - agent_id: идентификатор агента
        - capability: название способности
        - tags: дополнительные теги
        - session_id: идентификатор сессии
        - correlation_id: идентификатор корреляции
        - version: версия промпта/контракта
        - timestamp: время измерения
        - publish_event: публиковать ли событие в EventBus
        
        RETURNS:
        - MetricRecord: созданная запись метрики
        """
        metric = MetricRecord(
            agent_id=agent_id,
            capability=capability,
            metric_type=MetricType.GAUGE,
            name=name,
            value=value,
            timestamp=timestamp or datetime.now(),
            session_id=session_id,
            correlation_id=correlation_id,
            version=version,
            tags=tags or {}
        )
        
        await self._record_metric(metric, publish_event)
        return metric
    
    async def counter(
        self,
        name: str,
        value: float = 1.0,
        agent_id: str = "unknown",
        capability: str = "",
        tags: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        version: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        publish_event: bool = True
    ) -> MetricRecord:
        """
        Публикация метрики типа COUNTER.
        
        COUNTER метрики увеличиваются со временем (execution_count, error_count).
        
        ARGS:
        - name: имя метрики
        - value: значение для увеличения (по умолчанию 1.0)
        - agent_id: идентификатор агента
        - capability: название способности
        - tags: дополнительные теги
        - session_id: идентификатор сессии
        - correlation_id: идентификатор корреляции
        - version: версия промпта/контракта
        - timestamp: время измерения
        - publish_event: публиковать ли событие в EventBus
        
        RETURNS:
        - MetricRecord: созданная запись метрики
        """
        metric = MetricRecord(
            agent_id=agent_id,
            capability=capability,
            metric_type=MetricType.COUNTER,
            name=name,
            value=value,
            timestamp=timestamp or datetime.now(),
            session_id=session_id,
            correlation_id=correlation_id,
            version=version,
            tags=tags or {}
        )
        
        await self._record_metric(metric, publish_event)
        return metric
    
    async def histogram(
        self,
        name: str,
        value: float,
        agent_id: str = "unknown",
        capability: str = "",
        tags: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        version: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        publish_event: bool = True
    ) -> MetricRecord:
        """
        Публикация метрики типа HISTOGRAM.
        
        HISTOGRAM метрики представляют распределение значений (execution_time_ms, tokens_used).
        
        ARGS:
        - name: имя метрики
        - value: значение метрики
        - agent_id: идентификатор агента
        - capability: название способности
        - tags: дополнительные теги
        - session_id: идентификатор сессии
        - correlation_id: идентификатор корреляции
        - version: версия промпта/контракта
        - timestamp: время измерения
        - publish_event: публиковать ли событие в EventBus
        
        RETURNS:
        - MetricRecord: созданная запись метрики
        """
        metric = MetricRecord(
            agent_id=agent_id,
            capability=capability,
            metric_type=MetricType.HISTOGRAM,
            name=name,
            value=value,
            timestamp=timestamp or datetime.now(),
            session_id=session_id,
            correlation_id=correlation_id,
            version=version,
            tags=tags or {}
        )
        
        await self._record_metric(metric, publish_event)
        return metric
    
    async def record_custom(
        self,
        metric_type: Union[MetricType, str],
        name: str,
        value: float,
        agent_id: str = "unknown",
        capability: str = "",
        tags: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        version: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        publish_event: bool = True
    ) -> MetricRecord:
        """
        Публикация кастомной метрики с указанным типом.
        
        ARGS:
        - metric_type: тип метрики (MetricType или строка)
        - name: имя метрики
        - value: значение метрики
        - agent_id: идентификатор агента
        - capability: название способности
        - tags: дополнительные теги
        - session_id: идентификатор сессии
        - correlation_id: идентификатор корреляции
        - version: версия промпта/контракта
        - timestamp: время измерения
        - publish_event: публиковать ли событие в EventBus
        
        RETURNS:
        - MetricRecord: созданная запись метрики
        """
        if isinstance(metric_type, str):
            metric_type = MetricType(metric_type.lower())
        
        metric = MetricRecord(
            agent_id=agent_id,
            capability=capability,
            metric_type=metric_type,
            name=name,
            value=value,
            timestamp=timestamp or datetime.now(),
            session_id=session_id,
            correlation_id=correlation_id,
            version=version,
            tags=tags or {}
        )
        
        await self._record_metric(metric, publish_event)
        return metric
    
    async def _record_metric(self, metric: MetricRecord, publish_event: bool = True) -> None:
        """
        Внутренний метод для сохранения метрики и публикации события.
        
        ARGS:
        - metric: запись метрики
        - publish_event: публиковать ли событие в EventBus
        """
        # Сохранение в хранилище
        await self.storage.record(metric)
        
        # Публикация события в EventBus (если указано и EventBus доступен)
        if publish_event and self.event_bus:
            try:
                await self.event_bus.publish(
                    event=EventType.METRIC_COLLECTED,
                    data={
                        "agent_id": metric.agent_id,
                        "session_id": metric.session_id,
                        "capability": metric.capability,
                        "metric_type": metric.metric_type.value,
                        "name": metric.name,
                        "value": metric.value,
                        "version": metric.version,
                        "tags": metric.tags
                    },
                    source="MetricsPublisher",
                    correlation_id=metric.correlation_id
                )
            except Exception as e:
                # Не прерываем выполнение при ошибке публикации события
                # Логирование ошибки можно добавить при необходимости
                pass


# Утилиты для удобства использования

class MetricsContext:
    """
    Контекстный менеджер для измерения времени выполнения.
    
    ИСПОЛЬЗОВАНИЕ:
    ```python
    async with MetricsContext(publisher, "execution_time_ms", capability="sql_generation") as timer:
        # выполнение кода
        result = await some_operation()
    
    # Метрика будет автоматически опубликована при выходе из контекста
    ```
    """
    
    def __init__(
        self,
        publisher: MetricsPublisher,
        metric_name: str = "execution_time_ms",
        **metric_kwargs
    ):
        self.publisher = publisher
        self.metric_name = metric_name
        self.metric_kwargs = metric_kwargs
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = datetime.now()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            execution_time_ms = (datetime.now() - self.start_time).total_seconds() * 1000
            await self.publisher.histogram(
                name=self.metric_name,
                value=execution_time_ms,
                **self.metric_kwargs
            )
    
    def get_elapsed_ms(self) -> float:
        """
        Получение прошедшего времени в миллисекундах.
        
        RETURNS:
        - float: время в миллисекундах
        """
        if not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds() * 1000


def record_metrics(publisher: MetricsPublisher, metric_name: str, **default_kwargs):
    """
    Декоратор для автоматического сбора метрик выполнения функции.
    
    ИСПОЛЬЗОВАНИЕ:
    ```python
    @record_metrics(publisher, "function_execution_time", capability="data_analysis")
    async def analyze_data(data):
        # выполнение функции
        return result
    ```
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with MetricsContext(publisher, metric_name, **default_kwargs):
                return await func(*args, **kwargs)
        return wrapper
    return decorator