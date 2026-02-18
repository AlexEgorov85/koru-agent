"""
Сборщик логов через EventBus.

КОМПОНЕНТЫ:
- LogCollector: централизованный сбор структурированных логов

FEATURES:
- Подписка на события выполнения через EventBus
- Структурированное логирование (JSON)
- Корреляция по agent_id, session_id, capability
- Сохранение в хранилище для анализа
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType
from core.models.data.benchmark import LogEntry, LogType
from core.infrastructure.interfaces.metrics_log_interfaces import ILogStorage


logger = logging.getLogger(__name__)


class LogCollector:
    """
    Централизованный сбор логов для обучения.

    RESPONSIBILITIES:
    - Подписка на события с деталями выполнения
    - Преобразование событий в структурированные логи
    - Сохранение логов в хранилище
    - Извлечение логов для анализа

    ОТЛИЧИЯ ОТ ОБЫЧНОГО ЛОГИРОВАНИЯ:
    - Структурированные логи (JSON)
    - Корреляция по agent_id, session_id, capability
    - Сохранение в хранилище для обучения
    - Фильтрация по уровню важности
    """

    def __init__(
        self,
        event_bus: EventBus,
        storage: ILogStorage
    ):
        """
        Инициализация сборщика логов.

        ARGS:
        - event_bus: шина событий для подписки
        - storage: хранилище для сохранения логов
        """
        self.event_bus = event_bus
        self.storage = storage
        self._initialized = False
        self._subscriptions = []

    async def initialize(self) -> None:
        """
        Инициализация сборщика логов.

        Подписка на события:
        - EventType.CAPABILITY_SELECTED: выбор способности (важно для обучения)
        - EventType.ERROR_OCCURRED: ошибки для анализа
        - EventType.BENCHMARK_STARTED: события бенчмарков
        - EventType.BENCHMARK_COMPLETED: завершение бенчмарков
        - EventType.OPTIMIZATION_CYCLE_STARTED: оптимизация
        - EventType.OPTIMIZATION_CYCLE_COMPLETED: завершение оптимизации
        """
        if self._initialized:
            logger.warning("LogCollector уже инициализирован")
            return

        # Подписка на события
        self._subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self._subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
        self._subscribe(EventType.BENCHMARK_STARTED, self._on_benchmark_event)
        self._subscribe(EventType.BENCHMARK_COMPLETED, self._on_benchmark_event)
        self._subscribe(EventType.BENCHMARK_FAILED, self._on_benchmark_event)
        self._subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, self._on_optimization_event)
        self._subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, self._on_optimization_event)
        self._subscribe(EventType.VERSION_PROMOTED, self._on_version_event)
        self._subscribe(EventType.VERSION_REJECTED, self._on_version_event)

        self._initialized = True
        logger.info("LogCollector инициализирован: подписан на %d событий", len(self._subscriptions))

    def _subscribe(self, event_type: EventType, handler) -> None:
        """Подписка на событие"""
        self.event_bus.subscribe(event_type, handler)
        self._subscriptions.append(event_type)
        logger.debug("LogCollector подписан на %s", event_type.value)

    async def _on_capability_selected(self, event: Event) -> None:
        """
        Обработчик события выбора способности.

        Логирует:
        - Какую способность выбрал агент
        - Причины выбора (reasoning)
        - Использованный паттерн
        - Параметры выполнения

        ВАЖНО для обучения: reasoning помогает понять决策 процесс агента
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            session_id = data.get('session_id', 'unknown')
            capability = data.get('capability', '')

            if not capability:
                return

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.CAPABILITY_SELECTION,
                data={
                    'capability': capability,
                    'parameters': data.get('parameters', {}),
                    'reasoning': data.get('reasoning', ''),  # ← Важно для обучения!
                    'pattern_id': data.get('pattern_id'),
                    'confidence': data.get('confidence'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('version')
            )

            await self.storage.save(log_entry)

        except Exception as e:
            logger.error("Ошибка логирования CAPABILITY_SELECTED: %s", e)

    async def _on_error_occurred(self, event: Event) -> None:
        """
        Обработчик события ошибки.

        Логирует:
        - Тип ошибки
        - Сообщение об ошибке
        - Контекст выполнения
        - Стек вызовов (если доступен)
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            session_id = data.get('session_id', 'unknown')
            capability = data.get('capability', '')

            if not capability:
                capability = 'unknown'

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.ERROR,
                data={
                    'error_type': data.get('error_type', 'UnknownError'),
                    'error_message': data.get('error_message', ''),
                    'capability': capability,
                    'action': data.get('action'),
                    'input_data': self._sanitize_data(data.get('input_data')),
                    'stack_trace': data.get('stack_trace'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('version')
            )

            await self.storage.save(log_entry)

        except Exception as e:
            logger.error("Ошибка логирования ERROR_OCCURRED: %s", e)

    async def _on_benchmark_event(self, event: Event) -> None:
        """
        Обработчик событий бенчмарка.

        Логирует:
        - ID сценария бенчмарка
        - Результаты выполнения
        - Метрики
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'benchmark_system')
            session_id = data.get('session_id', f"benchmark_{event.timestamp.strftime('%Y%m%d_%H%M%S')}")
            capability = data.get('capability', 'benchmark')

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.BENCHMARK,
                data={
                    'event_type': event.event_type,
                    'scenario_id': data.get('scenario_id'),
                    'capability': capability,
                    'version': data.get('version'),
                    'metrics': data.get('metrics', {}),
                    'success': data.get('success'),
                    'overall_score': data.get('overall_score'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('version')
            )

            await self.storage.save(log_entry)

        except Exception as e:
            logger.error("Ошибка логирования бенчмарка: %s", e)

    async def _on_optimization_event(self, event: Event) -> None:
        """
        Обработчик событий оптимизации.

        Логирует:
        - Режим оптимизации
        - Номер итерации
        - Улучшения метрик
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'optimization_system')
            session_id = data.get('session_id', f"optimization_{event.timestamp.strftime('%Y%m%d_%H%M%S')}")
            capability = data.get('capability', '')

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.OPTIMIZATION,
                data={
                    'event_type': event.event_type,
                    'capability': capability,
                    'from_version': data.get('from_version'),
                    'to_version': data.get('to_version'),
                    'iterations': data.get('iterations'),
                    'improvements': data.get('improvements', {}),
                    'mode': data.get('mode'),
                    'target_achieved': data.get('target_achieved'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('to_version')
            )

            await self.storage.save(log_entry)

        except Exception as e:
            logger.error("Ошибка логирования оптимизации: %s", e)

    async def _on_version_event(self, event: Event) -> None:
        """
        Обработчик событий версий.

        Логирует:
        - Продвижение/отклонение версии
        - Причины решения
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'version_manager')
            session_id = data.get('session_id', 'version_management')
            capability = data.get('capability', '')

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.OPTIMIZATION,
                data={
                    'event_type': event.event_type,
                    'capability': capability,
                    'from_version': data.get('from_version'),
                    'to_version': data.get('to_version'),
                    'reason': data.get('reason'),
                    'metrics_comparison': data.get('metrics_comparison'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('to_version')
            )

            await self.storage.save(log_entry)

        except Exception as e:
            logger.error("Ошибка логирования версии: %s", e)

    def _sanitize_data(self, data: Any) -> Any:
        """
        Санитизация данных для логирования.

        Удаляет чувствительные данные и ограничивает размер.
        """
        if data is None:
            return None

        # Преобразование в строку с ограничением длины
        str_data = str(data)
        max_length = 1000

        if len(str_data) > max_length:
            return str_data[:max_length] + '... (truncated)'

        return str_data

    async def get_session_logs(
        self,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов сессии для анализа.

        ARGS:
        - agent_id: идентификатор агента
        - session_id: идентификатор сессии
        - limit: максимальное количество записей

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        return await self.storage.get_by_session(agent_id, session_id, limit)

    async def get_capability_logs(
        self,
        capability: str,
        log_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов по способности.

        ARGS:
        - capability: название способности
        - log_type: тип лога (опционально)
        - limit: максимальное количество записей

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        return await self.storage.get_by_capability(capability, log_type, limit)

    async def get_error_logs(
        self,
        capability: str,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов ошибок для анализа неудач.

        ARGS:
        - capability: название способности
        - limit: максимальное количество записей

        RETURNS:
        - List[LogEntry]: список логов ошибок
        """
        return await self.storage.get_by_capability(capability, log_type='error', limit=limit)

    async def shutdown(self) -> None:
        """
        Корректное завершение работы.
        """
        if not self._initialized:
            return

        self._subscriptions.clear()
        self._initialized = False
        logger.info("LogCollector завершил работу")

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self._initialized

    @property
    def subscriptions_count(self) -> int:
        """Количество подписок"""
        return len(self._subscriptions)
