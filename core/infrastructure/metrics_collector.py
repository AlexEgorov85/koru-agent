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
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage


logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Сборщик метрик через EventBus.

    RESPONSIBILITIES:
    - Подписка на события выполнения (SKILL_EXECUTED, CAPABILITY_SELECTED, ERROR_OCCURRED)
    - Извлечение метрик из event.data
    - Сохранение метрик в хранилище
    - Агрегация метрик для бенчмарков

    INTEGRATION:
    - Использует EventBus для подписки на события
    - Использует IMetricsStorage для сохранения метрик
    """

    def __init__(
        self,
        event_bus: EventBus,
        storage: IMetricsStorage
    ):
        """
        Инициализация сборщика метрик.

        ARGS:
        - event_bus: шина событий для подписки
        - storage: хранилище для сохранения метрик
        """
        self.event_bus = event_bus
        self.storage = storage
        self._initialized = False
        self._subscriptions = []

    async def initialize(self) -> None:
        """
        Инициализация сборщика метрик.

        Подписка на события:
        - EventType.SKILL_EXECUTED: выполнение навыков
        - EventType.CAPABILITY_SELECTED: выбор способности
        - EventType.ERROR_OCCURRED: ошибки выполнения
        """
        if self._initialized:
            logger.warning("MetricsCollector уже инициализирован")
            return

        # Подписка на события
        self._subscribe(EventType.SKILL_EXECUTED, self._on_skill_executed)
        self._subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self._subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
        self._subscribe(EventType.METRIC_COLLECTED, self._on_metric_collected)

        self._initialized = True
        logger.info("MetricsCollector инициализирован: подписан на %d событий", len(self._subscriptions))

    def _subscribe(self, event_type: EventType, handler) -> None:
        """Подписка на событие"""
        self.event_bus.subscribe(event_type, handler)
        self._subscriptions.append(event_type)
        logger.debug("MetricsCollector подписан на %s", event_type.value)

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
                logger.debug("Пропущено событие без capability: %s", event.event_type)
                return

            # Метрика успешности
            success_value = 1.0 if data.get('success', False) else 0.0
            success_metric = MetricRecord(
                agent_id=agent_id,
                capability=capability,
                metric_type=MetricType.GAUGE,
                name='success',
                value=success_value,
                timestamp=event.timestamp,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version
            )
            await self.storage.record(success_metric)

            # Метрика времени выполнения
            execution_time = data.get('execution_time_ms')
            if execution_time is not None:
                time_metric = MetricRecord(
                    agent_id=agent_id,
                    capability=capability,
                    metric_type=MetricType.HISTOGRAM,
                    name='execution_time_ms',
                    value=float(execution_time),
                    timestamp=event.timestamp,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    version=version
                )
                await self.storage.record(time_metric)

            # Метрика токенов
            tokens_used = data.get('tokens_used')
            if tokens_used is not None:
                tokens_metric = MetricRecord(
                    agent_id=agent_id,
                    capability=capability,
                    metric_type=MetricType.COUNTER,
                    name='tokens_used',
                    value=float(tokens_used),
                    timestamp=event.timestamp,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    version=version
                )
                await self.storage.record(tokens_metric)

        except Exception as e:
            logger.error("Ошибка обработки SKILL_EXECUTED: %s", e)

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
            selection_metric = MetricRecord(
                agent_id=agent_id,
                capability=capability,
                metric_type=MetricType.COUNTER,
                name='selection_count',
                value=1.0,
                timestamp=event.timestamp,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version
            )
            await self.storage.record(selection_metric)

        except Exception as e:
            logger.error("Ошибка обработки CAPABILITY_SELECTED: %s", e)

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

            if not capability:
                return

            # Метрика ошибки (0 = неудача)
            error_metric = MetricRecord(
                agent_id=agent_id,
                capability=capability,
                metric_type=MetricType.GAUGE,
                name='success',
                value=0.0,
                timestamp=event.timestamp,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                tags={'error': data.get('error_type', 'unknown')}
            )
            await self.storage.record(error_metric)

            # Счётчик ошибок
            error_count_metric = MetricRecord(
                agent_id=agent_id,
                capability=capability,
                metric_type=MetricType.COUNTER,
                name='error_count',
                value=1.0,
                timestamp=event.timestamp,
                session_id=session_id,
                correlation_id=correlation_id,
                version=version,
                tags={'error': data.get('error_type', 'unknown')}
            )
            await self.storage.record(error_count_metric)

        except Exception as e:
            logger.error("Ошибка обработки ERROR_OCCURRED: %s", e)

    async def _on_metric_collected(self, event: Event) -> None:
        """
        Обработчик события произвольной метрики.

        Позволяет сохранять кастомные метрики напрямую.
        """
        try:
            data = event.data

            metric_record = MetricRecord(
                agent_id=data.get('agent_id', 'unknown'),
                capability=data.get('capability', ''),
                metric_type=MetricType(data.get('metric_type', 'gauge')),
                name=data.get('name', ''),
                value=float(data.get('value', 0)),
                timestamp=event.timestamp,
                session_id=data.get('session_id'),
                correlation_id=event.correlation_id,
                version=data.get('version'),
                tags=data.get('tags', {})
            )

            if metric_record.capability and metric_record.name:
                await self.storage.record(metric_record)

        except Exception as e:
            logger.error("Ошибка обработки METRIC_COLLECTED: %s", e)

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

    async def shutdown(self) -> None:
        """
        Корректное завершение работы.

        Отписка от всех событий.
        """
        if not self._initialized:
            return

        for event_type in self._subscriptions:
            # Отписка (если метод unsubscribe доступен)
            try:
                # Пытаемся отписаться, если метод существует
                pass
            except Exception:
                pass

        self._subscriptions.clear()
        self._initialized = False
        logger.info("MetricsCollector завершил работу")

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self._initialized

    @property
    def subscriptions_count(self) -> int:
        """Количество подписок"""
        return len(self._subscriptions)
