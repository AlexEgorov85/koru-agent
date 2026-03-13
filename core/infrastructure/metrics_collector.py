"""
Сборщик метрик через EventBus.

КОМПОНЕНТЫ:
- MetricsCollector: сбор и агрегация метрик выполнения

FEATURES:
- Подписка на события выполнения через EventBus
- Извлечение метрик из событий
- Агрегация метрик для бенчмарков
- Централизованный сбор со всех агентов
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage
from core.infrastructure.collectors.base.base_collector import BaseEventCollector
from core.application.services.metrics_publisher import MetricsPublisher


class MetricsCollector(BaseEventCollector):
    """
    Сборщик метрик через EventBus.

    RESPONSIBILITIES:
    - Подписка на события выполнения (SKILL_EXECUTED, CAPABILITY_SELECTED, ERROR_OCCURRED)
    - Извлечение метрик из event.data
    - Сохранение метрик в хранилище через MetricsPublisher
    - Агрегация метрик для бенчмарков

    INTEGRATION:
    - Использует EventBus для подписки на события
    - Использует MetricsPublisher для публикации метрик
    - Совместим со старым IMetricsStorage через publisher
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        storage: IMetricsStorage,
        metrics_publisher: Optional[MetricsPublisher] = None
    ):
        """
        Инициализация сборщика метрик.

        ARGS:
        - event_bus: шина событий для подписки
        - storage: хранилище для сохранения метрик (для обратной совместимости)
        - metrics_publisher: публикатор метрик (опционально, создаётся автоматически)
        """
        super().__init__(event_bus, component_name="MetricsCollector")
        self.storage = storage
        # Создаём MetricsPublisher если не предоставлен
        self.publisher = metrics_publisher or MetricsPublisher(storage, event_bus)

    async def initialize(self) -> None:
        """
        Инициализация сборщика метрик.

        Подписка на события:
        - EventType.SKILL_EXECUTED: выполнение навыков
        - EventType.CAPABILITY_SELECTED: выбор способности
        - EventType.ERROR_OCCURRED: ошибки выполнения
        - EventType.METRIC_COLLECTED: произвольные метрики
        """
        if self._initialized:
            self.event_bus_logger.warning("MetricsCollector уже инициализирован")
            return

        # Подписка на события
        self._subscribe(EventType.SKILL_EXECUTED, self._on_skill_executed)
        self._subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self._subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
        self._subscribe(EventType.METRIC_COLLECTED, self._on_metric_collected)

        await super().initialize()

    async def _on_skill_executed(self, event: Event) -> None:
        """
        Обработчик события выполнения навыка.

        Извлекает метрики из event.data:
        - agent_id: идентификатор агента
        - capability: название способности
        - execution_time_ms: время выполнения
        - success: успешность (1.0/0.0)
        - tokens_used: количество токенов
        - session_id: идентификатор сессии
        - version: версия промпта/контракта
        """
        try:
            data = event.data

            # Извлечение основных метрик
            agent_id = data.get('agent_id', 'unknown')
            capability = data.get('capability', '')
            session_id = data.get('session_id')
            correlation_id = event.correlation_id
            version = data.get('version')

            if not capability:
                self.event_bus_logger.debug("Пропущено событие без capability: %s", event.event_type)
                return

            # Метрика успешности
            success_value = 1.0 if data.get('success', False) else 0.0
            
            # НОВЫЙ API: MetricsPublisher
            await self.publisher.gauge(
                name='success',
                value=success_value,
                agent_id=agent_id,
                capability=capability,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                timestamp=event.timestamp,
                publish_event=False  # Не публиковать событие, т.к. это уже обработчик события
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.storage.record(MetricRecord(
            #     agent_id=agent_id,
            #     capability=capability,
            #     metric_type=MetricType.GAUGE,
            #     name='success',
            #     value=success_value,
            #     timestamp=event.timestamp,
            #     session_id=session_id,
            #     correlation_id=correlation_id,
            #     version=version
            # ))

            # Публикуем событие для SessionLogHandler (сохраняем обратную совместимость)
            await self.event_bus.publish(
                event=EventType.METRIC_COLLECTED,
                data={
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "capability": capability,
                    "metric_type": "gauge",
                    "name": "success",
                    "value": success_value,
                    "version": version
                },
                source="MetricsCollector"
            )

            # Метрика времени выполнения
            execution_time = data.get('execution_time_ms')
            if execution_time is not None:
                # НОВЫЙ API: MetricsPublisher
                await self.publisher.histogram(
                    name='execution_time_ms',
                    value=float(execution_time),
                    agent_id=agent_id,
                    capability=capability,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    version=version,
                    timestamp=event.timestamp,
                    publish_event=False
                )

                # СТАРЫЙ API (закомментирован для обратной совместимости):
                # await self.storage.record(MetricRecord(
                #     agent_id=agent_id,
                #     capability=capability,
                #     metric_type=MetricType.HISTOGRAM,
                #     name='execution_time_ms',
                #     value=float(execution_time),
                #     timestamp=event.timestamp,
                #     session_id=session_id,
                #     correlation_id=correlation_id,
                #     version=version
                # ))

                # Публикуем событие для SessionLogHandler
                await self.event_bus.publish(
                    event=EventType.METRIC_COLLECTED,
                    data={
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "capability": capability,
                        "metric_type": "histogram",
                        "name": "execution_time_ms",
                        "value": float(execution_time),
                        "version": version
                    },
                    source="MetricsCollector"
                )

            # Метрика токенов
            tokens_used = data.get('tokens_used')
            if tokens_used is not None:
                # НОВЫЙ API: MetricsPublisher
                await self.publisher.counter(
                    name='tokens_used',
                    value=float(tokens_used),
                    agent_id=agent_id,
                    capability=capability,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    version=version,
                    timestamp=event.timestamp,
                    publish_event=False
                )

                # СТАРЫЙ API (закомментирован для обратной совместимости):
                # await self.storage.record(MetricRecord(
                #     agent_id=agent_id,
                #     capability=capability,
                #     metric_type=MetricType.COUNTER,
                #     name='tokens_used',
                #     value=float(tokens_used),
                #     timestamp=event.timestamp,
                #     session_id=session_id,
                #     correlation_id=correlation_id,
                #     version=version
                # ))

                # Публикуем событие для SessionLogHandler
                await self.event_bus.publish(
                    event=EventType.METRIC_COLLECTED,
                    data={
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "capability": capability,
                        "metric_type": "counter",
                        "name": "tokens_used",
                        "value": float(tokens_used),
                        "version": version
                    },
                    source="MetricsCollector"
                )

        except Exception as e:
            self.event_bus_logger.error("Ошибка обработки SKILL_EXECUTED: %s", e)

    async def _on_capability_selected(self, event: Event) -> None:
        """
        Обработчик события выбора способности.

        Извлекает метрики:
        - capability: выбранная способность
        - pattern_id: использованный паттерн
        - reasoning: причина выбора (для логов)
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            capability = data.get('capability', '')
            session_id = data.get('session_id')
            correlation_id = event.correlation_id
            version = data.get('version')

            if not capability:
                return

            # Счётчик выбора способности
            # НОВЫЙ API: MetricsPublisher
            await self.publisher.counter(
                name='selection_count',
                value=1.0,
                agent_id=agent_id,
                capability=capability,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                timestamp=event.timestamp,
                publish_event=False
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.storage.record(MetricRecord(
            #     agent_id=agent_id,
            #     capability=capability,
            #     metric_type=MetricType.COUNTER,
            #     name='selection_count',
            #     value=1.0,
            #     timestamp=event.timestamp,
            #     session_id=session_id,
            #     correlation_id=correlation_id,
            #     version=version
            # ))

        except Exception as e:
            self.event_bus_logger.error("Ошибка обработки CAPABILITY_SELECTED: %s", e)

    async def _on_error_occurred(self, event: Event) -> None:
        """
        Обработчик события ошибки.

        Извлекает метрики:
        - capability: способность где произошла ошибка
        - error_type: тип ошибки
        - agent_id: идентификатор агента
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            capability = data.get('capability', '')
            session_id = data.get('session_id')
            correlation_id = event.correlation_id
            version = data.get('version')
            error_type = data.get('error_type', 'unknown')

            if not capability:
                return

            # Метрика ошибки (0 = неудача)
            # НОВЫЙ API: MetricsPublisher
            await self.publisher.gauge(
                name='success',
                value=0.0,
                agent_id=agent_id,
                capability=capability,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                timestamp=event.timestamp,
                tags={'error': error_type},
                publish_event=False
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.storage.record(MetricRecord(
            #     agent_id=agent_id,
            #     capability=capability,
            #     metric_type=MetricType.GAUGE,
            #     name='success',
            #     value=0.0,
            #     timestamp=event.timestamp,
            #     session_id=session_id,
            #     correlation_id=correlation_id,
            #     version=version,
            #     tags={'error': error_type}
            # ))

            # Счётчик ошибок
            # НОВЫЙ API: MetricsPublisher
            await self.publisher.counter(
                name='error_count',
                value=1.0,
                agent_id=agent_id,
                capability=capability,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                timestamp=event.timestamp,
                tags={'error': error_type},
                publish_event=False
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.storage.record(MetricRecord(
            #     agent_id=agent_id,
            #     capability=capability,
            #     metric_type=MetricType.COUNTER,
            #     name='error_count',
            #     value=1.0,
            #     timestamp=event.timestamp,
            #     session_id=session_id,
            #     correlation_id=correlation_id,
            #     version=version,
            #     tags={'error': error_type}
            # ))

        except Exception as e:
            self.event_bus_logger.error("Ошибка обработки ERROR_OCCURRED: %s", e)

    async def _on_metric_collected(self, event: Event) -> None:
        """
        Обработчик события произвольной метрики.

        Позволяет сохранять кастомные метрики напрямую.
        """
        try:
            data = event.data

            metric_type = data.get('metric_type', 'gauge')
            name = data.get('name', '')
            value = float(data.get('value', 0))
            agent_id = data.get('agent_id', 'unknown')
            capability = data.get('capability', '')
            session_id = data.get('session_id')
            correlation_id = event.correlation_id
            version = data.get('version')
            tags = data.get('tags', {})

            if capability and name:
                # НОВЫЙ API: MetricsPublisher
                await self.publisher.record_custom(
                    metric_type=metric_type,
                    name=name,
                    value=value,
                    agent_id=agent_id,
                    capability=capability,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    version=version,
                    timestamp=event.timestamp,
                    tags=tags,
                    publish_event=False  # Это уже обработчик события METRIC_COLLECTED
                )

                # СТАРЫЙ API (закомментирован для обратной совместимости):
                # await self.storage.record(MetricRecord(
                #     agent_id=agent_id,
                #     capability=capability,
                #     metric_type=MetricType(metric_type.lower()),
                #     name=name,
                #     value=value,
                #     timestamp=event.timestamp,
                #     session_id=session_id,
                #     correlation_id=correlation_id,
                #     version=version,
                #     tags=tags
                # ))

        except Exception as e:
            self.event_bus_logger.error("Ошибка обработки METRIC_COLLECTED: %s", e)

    async def get_aggregated_metrics(
        self,
        capability: str,
        version: str,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> AggregatedMetrics:
        """
        Получение агрегированных метрик для бенчмарка.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта
        - time_range: временной диапазон (start, end)

        RETURNS:
        - AggregatedMetrics: агрегированные метрики
        """
        return await self.storage.aggregate(capability, version, time_range)

    async def get_metrics(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[MetricRecord]:
        """
        Получение сырых метрик.

        ARGS:
        - capability: название способности
        - version: версия (опционально)
        - time_range: временной диапазон (опционально)
        - limit: ограничение количества (опционально)

        RETURNS:
        - List[MetricRecord]: список метрик
        """
        return await self.storage.get_records(capability, version, time_range, limit)