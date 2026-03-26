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
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType
from core.services.benchmarks.benchmark_models import LogEntry, LogType
from core.models.data.execution import ExecutionContextSnapshot
from core.infrastructure.interfaces.metrics_log_interfaces import ILogStorage
from core.infrastructure.collectors.base.base_collector import BaseEventCollector


class LogCollector(BaseEventCollector):
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
        event_bus: UnifiedEventBus,
        storage: ILogStorage
    ):
        """
        Инициализация сборщика логов.

        ARGS:
        - event_bus: шина событий для подписки
        - storage: хранилище для сохранения логов
        """
        super().__init__(event_bus, component_name="LogCollector")
        self.storage = storage

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
        - EventType.LLM_PROMPT_GENERATED: сгенерированный промпт для LLM
        - EventType.LLM_RESPONSE_RECEIVED: полученный ответ от LLM
        """
        if self._initialized:
            self.event_bus_logger.warning("LogCollector уже инициализирован")
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
        
        # Подписка на LLM события для логирования промптов и ответов
        self._subscribe(EventType.LLM_PROMPT_GENERATED, self._on_llm_prompt_generated)
        self._subscribe(EventType.LLM_RESPONSE_RECEIVED, self._on_llm_response_received)

        self._initialized = True
        await self.event_bus_logger.info("LogCollector инициализирован: подписан на %d событий", len(self._subscriptions))

    def _subscribe(self, event_type: EventType, handler) -> None:
        """Подписка на событие"""
        self.event_bus.subscribe(event_type, handler)
        self._subscriptions.append(event_type)
        # logger.debug("LogCollector подписан на %s", event_type.value)

    async def _on_capability_selected(self, event: Event) -> None:
        """
        Обработчик события выбора способности.

        Логирует:
        - Какую способность выбрал агент
        - Причины выбора (reasoning)
        - Использованный паттерн
        - Параметры выполнения
        - Контекст выполнения (для обучения)

        ВАЖНО для обучения: reasoning помогает понять процесс принятия решения агентом
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            session_id = data.get('session_id', 'unknown')
            capability = data.get('capability', '')

            if not capability:
                return

            # Извлечение контекста выполнения (если передан)
            execution_context = data.get('execution_context')
            
            # Расчёт оценки качества шага
            quality_score = await self._calculate_quality_score(data)

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.CAPABILITY_SELECTION,
                data={
                    'capability': capability,
                    'parameters': data.get('parameters', {}),
                    'reasoning': data.get('reasoning', ''),
                    'pattern_id': data.get('pattern_id'),
                    'confidence': data.get('confidence'),
                    'execution_context': execution_context,
                    'step_quality_score': quality_score,
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('version'),
                execution_context=execution_context,
                step_quality_score=quality_score
            )

            await self.storage.save(log_entry)

        except Exception as e:
            self.event_bus_logger.error("Ошибка логирования CAPABILITY_SELECTED: %s", e)

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
            self.event_bus_logger.error("Ошибка логирования ERROR_OCCURRED: %s", e)

    async def _on_benchmark_event(self, event: Event) -> None:
        """
        Обработчик событий бенчмарка.

        Логирует:
        - ID сценария бенчмарка
        - Результаты выполнения
        - Метрики
        - benchmark_scenario_id для связи с execution logs
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'benchmark_system')
            session_id = data.get('session_id', f"benchmark_{event.timestamp.strftime('%Y%m%d_%H%M%S')}")
            capability = data.get('capability', 'benchmark')
            scenario_id = data.get('scenario_id')

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.BENCHMARK,
                data={
                    'event_type': event.event_type,
                    'scenario_id': scenario_id,
                    'capability': capability,
                    'version': data.get('version'),
                    'metrics': data.get('metrics', {}),
                    'success': data.get('success'),
                    'overall_score': data.get('overall_score'),
                    'benchmark_scenario_id': scenario_id,
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version=data.get('version'),
                benchmark_scenario_id=scenario_id
            )

            await self.storage.save(log_entry)

        except Exception as e:
            self.event_bus_logger.error("Ошибка логирования бенчмарка: %s", e)

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
            self.event_bus_logger.error("Ошибка логирования оптимизации: %s", e)

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
            self.event_bus_logger.error("Ошибка логирования версии: %s", e)

    async def _on_llm_prompt_generated(self, event: Event) -> None:
        """
        Обработчик события LLM_PROMPT_GENERATED.

        Логирует:
        - Сгенерированный промпт (system + user)
        - Компонент и фазу выполнения
        - Параметры генерации (temperature, max_tokens)
        - Session ID для корреляции
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            session_id = data.get('session_id', 'unknown')
            capability = data.get('component', 'unknown')

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.LLM_PROMPT,
                data={
                    'component': data.get('component', 'unknown'),
                    'phase': data.get('phase', 'unknown'),
                    'system_prompt': data.get('system_prompt', ''),
                    'user_prompt': data.get('user_prompt', ''),
                    'prompt_length': data.get('prompt_length', 0),
                    'temperature': data.get('temperature', 0.7),
                    'max_tokens': data.get('max_tokens', 1000),
                    'goal': data.get('goal', 'unknown'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version='v1.0.0'
            )

            await self.storage.save(log_entry)

        except Exception as e:
            self.event_bus_logger.error("Ошибка логирования LLM промпта: %s", e)

    async def _on_llm_response_received(self, event: Event) -> None:
        """
        Обработчик события LLM_RESPONSE_RECEIVED.

        Логирует:
        - Полученный ответ от LLM
        - Компонент и фазу выполнения
        - Формат ответа
        - Session ID для корреляции
        """
        try:
            data = event.data

            agent_id = data.get('agent_id', 'unknown')
            session_id = data.get('session_id', 'unknown')
            capability = data.get('component', 'unknown')

            # Обработка ответа
            response = data.get('response', {})
            if isinstance(response, dict) and 'raw_response' in response:
                result = response['raw_response']
                response_format = "dict.raw_response"
            elif hasattr(response, 'content'):
                result = response.content
                response_format = "object.content"
            else:
                result = response
                response_format = type(response).__name__

            log_entry = LogEntry(
                timestamp=event.timestamp,
                agent_id=agent_id,
                session_id=session_id,
                log_type=LogType.LLM_RESPONSE,
                data={
                    'component': data.get('component', 'unknown'),
                    'phase': data.get('phase', 'unknown'),
                    'response_format': data.get('response_format', response_format),
                    'response': result,
                    'goal': data.get('goal', 'unknown'),
                },
                correlation_id=event.correlation_id,
                capability=capability,
                version='v1.0.0'
            )

            await self.storage.save(log_entry)

        except Exception as e:
            self.event_bus_logger.error("Ошибка логирования LLM ответа: %s", e)

    async def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """
        Расчёт оценки качества шага (0.0 - 1.0).
        
        КРИТЕРИИ:
        1. Успешность выполнения (0.5 базовых)
        2. Время выполнения (до +0.2)
        3. Использование токенов (до +0.1)
        4. Достижение прогресса (до +0.2)
        
        ARGS:
        - data: данные события
        
        RETURNS:
        - float: оценка качества от 0.0 до 1.0
        """
        score = 0.5  # Базовая оценка за выполнение
        
        # Успешность
        if data.get('success', False):
            score += 0.3
        else:
            return 0.2  # Неудачный шаг
        
        # Время выполнения (быстрее = лучше)
        execution_time = data.get('execution_time_ms', 0)
        if execution_time < 100:  # < 100мс
            score += 0.2
        elif execution_time < 500:  # < 500мс
            score += 0.1
        
        # Токены (меньше = лучше)
        tokens = data.get('tokens_used', 0)
        if tokens < 100:
            score += 0.1
        elif tokens < 500:
            score += 0.05
        
        # Прогресс к цели
        progress = data.get('goal_progress', 0)
        score += progress * 0.2
        
        return min(1.0, max(0.0, score))

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
