"""
UnifiedEventBus — единая шина событий с поддержкой:
- Session isolation (как EventBusConcurrent)
- Domain routing (как EventBusManager)
- Backward compatibility (как EventBus)

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedEventBus                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Session Workers (изолированные очереди)              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │Session A│ │Session B│ │Session C│ │  ...    │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Domain Routing (внутри одной шины)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  event.domain → фильтр подписчиков                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

FEATURES:
- ✅ Session isolation — события сессии A не видны сессии B
- ✅ Domain routing — подписка на события конкретных доменов
- ✅ FIFO порядок внутри сессии
- ✅ Backpressure — ограничение размера очереди
- ✅ No event duplication — событие не дублируется между шинами
- ✅ Backward compatibility — поддержка старого API

USAGE:
```python
# Базовое использование
from core.infrastructure.event_bus.unified_event_bus import get_event_bus

event_bus = get_event_bus()

# Подписка на событие
event_bus.subscribe(EventType.AGENT_STARTED, handler)

# Подписка с фильтром по домену
event_bus.subscribe(EventType.AGENT_STARTED, handler, domain=EventDomain.AGENT)

# Подписка с фильтром по сессии
event_bus.subscribe(EventType.AGENT_STARTED, handler, session_id="session_123")

# Публикация события
await event_bus.publish(
    EventType.AGENT_STARTED,
    data={"agent_id": "123"},
    session_id="session_123",
    domain=EventDomain.AGENT
)
```
"""
import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

DEFAULT_QUEUE_MAX_SIZE = 1000
DEFAULT_WORKER_IDLE_TIMEOUT = 60.0
DEFAULT_SUBSCRIBER_TIMEOUT = 60.0  # Таймаут подписчиков (LLM timeout настраивается отдельно)
SYSTEM_SESSION_ID = "system"  # Единая системная сессия для всех событий без session_id


# =============================================================================
# ТИПЫ СОБЫТИЙ И ДОМЕНЫ
# =============================================================================

class EventType(Enum):
    """Типы событий в системе."""
    # === Системные события ===
    SYSTEM_INITIALIZED = "system.initialized"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # === События жизненного цикла сессии ===
    SESSION_CREATED = "session.created"
    SESSION_STARTED = "session.started"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"
    SESSION_CLOSED = "session.closed"

    # === События жизненного цикла агента ===
    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # === События выполнения ===
    CAPABILITY_SELECTED = "capability.selected"
    SKILL_EXECUTED = "skill.executed"
    ACTION_PERFORMED = "action.performed"
    STEP_REGISTERED = "step.registered"

    # === События контекста ===
    CONTEXT_ITEM_ADDED = "context.item.added"
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"

    # === События провайдеров ===
    PROVIDER_REGISTERED = "provider.registered"
    PROVIDER_UNREGISTERED = "provider.unregistered"
    LLM_CALL_STARTED = "llm.call.started"
    LLM_CALL_COMPLETED = "llm.call.completed"
    LLM_CALL_FAILED = "llm.call.failed"
    LLM_PROMPT_GENERATED = "llm.prompt.generated"
    LLM_RESPONSE_RECEIVED = "llm.response.received"

    # === События сервисов ===
    SERVICE_REGISTERED = "service.registered"
    SERVICE_INITIALIZED = "service.initialized"
    SERVICE_SHUTDOWN = "service.shutdown"
    SERVICE_ERROR = "service.error"

    # === События ошибок ===
    RETRY_ATTEMPT = "retry.attempt"
    ERROR_OCCURRED = "error.occurred"

    # === События метрик ===
    METRIC_COLLECTED = "metric.collected"

    # === События бенчмарков ===
    BENCHMARK_STARTED = "benchmark.started"
    BENCHMARK_COMPLETED = "benchmark.completed"
    BENCHMARK_FAILED = "benchmark.failed"

    # === События оптимизации ===
    OPTIMIZATION_CYCLE_STARTED = "optimization.cycle.started"
    OPTIMIZATION_CYCLE_COMPLETED = "optimization.cycle.completed"
    OPTIMIZATION_FAILED = "optimization.failed"

    # === События самообучения (Self-Improvement) ===
    SELF_IMPROVEMENT_STARTED = "self_improvement.started"
    SELF_IMPROVEMENT_THINKING_STARTED = "self_improvement.thinking.started"
    SELF_IMPROVEMENT_THINKING_COMPLETED = "self_improvement.thinking.completed"
    SELF_IMPROVEMENT_DECISION = "self_improvement.decision"
    SELF_IMPROVEMENT_ACTION_STARTED = "self_improvement.action.started"
    SELF_IMPROVEMENT_ACTION_COMPLETED = "self_improvement.action.completed"
    SELF_IMPROVEMENT_REPORT = "self_improvement.report"
    SELF_IMPROVEMENT_COMPLETED = "self_improvement.completed"
    SELF_IMPROVEMENT_FAILED = "self_improvement.failed"

    # === События версий ===
    VERSION_PROMOTED = "version.promoted"
    VERSION_REJECTED = "version.rejected"
    VERSION_CREATED = "version.created"

    # === События универсального логирования ===
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    COMPONENT_INITIALIZED = "component.initialized"
    COMPONENT_SHUTDOWN = "component.shutdown"

    # === События логирования ===
    LOG_INFO = "log.info"
    LOG_DEBUG = "log.debug"
    LOG_WARNING = "log.warning"
    LOG_ERROR = "log.error"

    # === Пользовательские сообщения (вывод в терминал) ===
    USER_MESSAGE = "user.message"  # Важные сообщения для пользователя
    USER_PROGRESS = "user.progress"  # Прогресс выполнения
    USER_RESULT = "user.result"  # Результаты выполнения

    # === Telemetry события ===
    WORKER_CREATED = "worker.created"
    WORKER_STARTED = "worker.started"
    WORKER_IDLE = "worker.idle"
    WORKER_CRASHED = "worker.crashed"
    WORKER_CLOSED = "worker.closed"
    SUBSCRIBER_FAILED = "subscriber.failed"
    QUEUE_OVERFLOW = "queue.overflow"


class EventDomain(Enum):
    """Домены событий для изоляции компонентов."""
    AGENT = "agent"
    BENCHMARK = "benchmark"
    INFRASTRUCTURE = "infrastructure"
    OPTIMIZATION = "optimization"
    SECURITY = "security"
    COMMON = "common"


# Маппинг типов событий на домены
EVENT_TYPE_TO_DOMAIN: Dict[EventType, EventDomain] = {
    # Agent domain
    EventType.AGENT_CREATED: EventDomain.AGENT,
    EventType.AGENT_STARTED: EventDomain.AGENT,
    EventType.AGENT_COMPLETED: EventDomain.AGENT,
    EventType.AGENT_FAILED: EventDomain.AGENT,
    EventType.CAPABILITY_SELECTED: EventDomain.AGENT,
    EventType.SKILL_EXECUTED: EventDomain.AGENT,
    EventType.ACTION_PERFORMED: EventDomain.AGENT,
    EventType.STEP_REGISTERED: EventDomain.AGENT,
    EventType.CONTEXT_ITEM_ADDED: EventDomain.AGENT,
    EventType.PLAN_CREATED: EventDomain.AGENT,
    EventType.PLAN_UPDATED: EventDomain.AGENT,

    # Benchmark domain
    EventType.BENCHMARK_STARTED: EventDomain.BENCHMARK,
    EventType.BENCHMARK_COMPLETED: EventDomain.BENCHMARK,
    EventType.BENCHMARK_FAILED: EventDomain.BENCHMARK,

    # Infrastructure domain
    EventType.SYSTEM_INITIALIZED: EventDomain.INFRASTRUCTURE,
    EventType.SYSTEM_SHUTDOWN: EventDomain.INFRASTRUCTURE,
    EventType.SYSTEM_ERROR: EventDomain.INFRASTRUCTURE,
    EventType.PROVIDER_REGISTERED: EventDomain.INFRASTRUCTURE,
    EventType.PROVIDER_UNREGISTERED: EventDomain.INFRASTRUCTURE,
    EventType.LLM_CALL_STARTED: EventDomain.INFRASTRUCTURE,
    EventType.LLM_CALL_COMPLETED: EventDomain.INFRASTRUCTURE,
    EventType.LLM_CALL_FAILED: EventDomain.INFRASTRUCTURE,
    EventType.LLM_PROMPT_GENERATED: EventDomain.INFRASTRUCTURE,
    EventType.LLM_RESPONSE_RECEIVED: EventDomain.INFRASTRUCTURE,
    EventType.SERVICE_REGISTERED: EventDomain.INFRASTRUCTURE,
    EventType.SERVICE_INITIALIZED: EventDomain.INFRASTRUCTURE,
    EventType.SERVICE_SHUTDOWN: EventDomain.INFRASTRUCTURE,
    EventType.SERVICE_ERROR: EventDomain.INFRASTRUCTURE,
    EventType.COMPONENT_INITIALIZED: EventDomain.INFRASTRUCTURE,
    EventType.COMPONENT_SHUTDOWN: EventDomain.INFRASTRUCTURE,

    # Optimization domain
    EventType.OPTIMIZATION_CYCLE_STARTED: EventDomain.OPTIMIZATION,
    EventType.OPTIMIZATION_CYCLE_COMPLETED: EventDomain.OPTIMIZATION,
    EventType.OPTIMIZATION_FAILED: EventDomain.OPTIMIZATION,
    EventType.VERSION_PROMOTED: EventDomain.OPTIMIZATION,
    EventType.VERSION_REJECTED: EventDomain.OPTIMIZATION,
    EventType.VERSION_CREATED: EventDomain.OPTIMIZATION,
    # Self-improvement events
    EventType.SELF_IMPROVEMENT_STARTED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_THINKING_STARTED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_THINKING_COMPLETED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_DECISION: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_ACTION_STARTED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_ACTION_COMPLETED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_REPORT: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_COMPLETED: EventDomain.OPTIMIZATION,
    EventType.SELF_IMPROVEMENT_FAILED: EventDomain.OPTIMIZATION,

    # Common domain
    EventType.RETRY_ATTEMPT: EventDomain.COMMON,
    EventType.ERROR_OCCURRED: EventDomain.COMMON,
    EventType.METRIC_COLLECTED: EventDomain.COMMON,
    EventType.EXECUTION_STARTED: EventDomain.COMMON,
    EventType.EXECUTION_COMPLETED: EventDomain.COMMON,
    EventType.EXECUTION_FAILED: EventDomain.COMMON,
}


def get_event_domain(event_type: Union[str, EventType]) -> EventDomain:
    """Определение домена по типу события."""
    if isinstance(event_type, str):
        try:
            event_type = EventType(event_type)
        except ValueError:
            return EventDomain.COMMON
    return EVENT_TYPE_TO_DOMAIN.get(event_type, EventDomain.COMMON)


# =============================================================================
# СОБЫТИЕ
# =============================================================================

@dataclass
class Event:
    """
    Базовый класс события.

    ATTRIBUTES:
    - event_type: тип события
    - data: данные события
    - timestamp: время возникновения события
    - source: источник события
    - session_id: ID сессии (для маршрутизации)
    - agent_id: ID агента (для фильтрации)
    - correlation_id: идентификатор корреляции
    - sequence_number: порядковый номер в сессии
    - domain: домен события (для routing)
    """
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    session_id: str = ""
    agent_id: str = ""
    correlation_id: str = ""
    sequence_number: int = 0
    domain: EventDomain = EventDomain.COMMON

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if isinstance(self.domain, str):
            try:
                self.domain = EventDomain(self.domain)
            except ValueError:
                self.domain = EventDomain.COMMON


# =============================================================================
# МЕТАДАННЫЕ СЕССИИ
# =============================================================================

@dataclass
class SessionMeta:
    """Метаданные сессии."""
    session_id: str
    agent_id: str
    created_at: datetime
    last_event_at: datetime
    sequence_counter: int = 0
    event_count: int = 0
    is_active: bool = True


# =============================================================================
# DOMAIN FILTER
# =============================================================================

@dataclass
class SubscriberInfo:
    """Информация о подписчике."""
    handler: Callable
    domain: Optional[EventDomain] = None
    domains: Optional[List[EventDomain]] = None
    session_id: Optional[str] = None

    def matches(self, event: Event) -> bool:
        """Проверка соответствия подписчика событию."""
        # Фильтр по session_id
        if self.session_id and event.session_id != self.session_id:
            return False

        # Фильтр по домену
        if self.domain is not None:
            event_domain = event.domain if event.domain else get_event_domain(event.event_type)
            if event_domain != self.domain:
                return False

        # Фильтр по списку доменов (для subscribe_all)
        if self.domains is not None:
            event_domain = event.domain if event.domain else get_event_domain(event.event_type)
            if event_domain not in self.domains:
                return False

        return True


# =============================================================================
# SESSION WORKER
# =============================================================================

class SessionWorker:
    """
    Worker для обработки событий конкретной сессии.

    FEATURES:
    - Читает события из session_queue
    - Последовательно вызывает всех подписчиков
    - Увеличивает sequence_number
    - Авто-закрытие при простое
    """

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        queue: asyncio.Queue,
        subscribers: Dict[str, List[SubscriberInfo]],
        all_subscribers: List[SubscriberInfo],
        idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
        subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT,
        event_bus: "UnifiedEventBus" = None,
        session_bound: bool = False  # Worker живёт пока сессия активна
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        self._queue = queue
        self._subscribers = subscribers
        self._all_subscribers = all_subscribers
        self._idle_timeout = idle_timeout
        self._subscriber_timeout = subscriber_timeout
        self._event_bus = event_bus
        self._session_bound = session_bound  # ← НОВОЕ: режим привязки к сессии

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_activity = time.time()
        self._sequence_counter = 0
        self._processed_count = 0
        self._error_count = 0

        self._logger = logging.getLogger(f"{__name__}.SessionWorker[{session_id}]")

    async def start(self):
        """Запуск worker'а."""
        if self._task is not None:
            self._logger.warning("Worker уже запущен")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        
        # ← НОВОЕ: Показываем session_bound статус
        if self._session_bound:
            self._logger.debug(f"Worker запущен (session_bound=True, idle_timeout={self._idle_timeout}s)")
        else:
            self._logger.debug(f"Worker запущен (idle_timeout={self._idle_timeout}s)")

        if self._event_bus:
            await self._event_bus._publish_internal(
                EventType.WORKER_CREATED,
                {
                    "session_id": self.session_id,
                    "agent_id": self.agent_id,
                    "queue_size": self._queue.qsize()
                }
            )

    async def _run(self):
        """Основной цикл worker'а."""
        # Логирование уже было в start()

        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._idle_timeout
                    )

                    # ← НОВОЕ: Проверка на завершение сессии для session_bound worker'а
                    if (self._session_bound and 
                        event.event_type == EventType.SESSION_COMPLETED.value and
                        event.data.get('session_id') == self.session_id):
                        self._logger.info(f"Сессия {self.session_id} завершена, остановка worker'а")
                        self._queue.task_done()
                        break
                    
                    # ← НОВОЕ: Проверка на закрытие сессии
                    if (self._session_bound and 
                        event.event_type == EventType.SESSION_CLOSED.value and
                        event.data.get('session_id') == self.session_id):
                        self._logger.info(f"Сессия {self.session_id} закрыта, остановка worker'а")
                        self._queue.task_done()
                        break

                    await self._process_event(event)
                    self._last_activity = time.time()
                    self._queue.task_done()

                except asyncio.TimeoutError:
                    idle_time = time.time() - self._last_activity
                    if idle_time >= self._idle_timeout:
                        # ← НОВОЕ: session_bound worker не завершается по idle timeout
                        if self._session_bound:
                            self._logger.debug(
                                f"Idle timeout ({idle_time:.1f}s), но worker session_bound - продолжаем ждать"
                            )
                            continue  # ← Продолжаем ждать вместо break
                        
                        self._logger.debug(f"Idle timeout ({idle_time:.1f}s), завершение worker'а")
                        if self._event_bus:
                            await self._event_bus._publish_internal(
                                EventType.WORKER_IDLE,
                                {
                                    "session_id": self.session_id,
                                    "idle_seconds": idle_time,
                                    "processed_count": self._processed_count
                                }
                            )
                        break

                except asyncio.CancelledError:
                    self._logger.debug("Worker отменён")
                    break

                except Exception as e:
                    self._logger.error(f"Ошибка в цикле worker'а: {e}", exc_info=True)
                    self._error_count += 1

        except Exception as e:
            self._logger.error(f"Критическая ошибка worker'а: {e}", exc_info=True)
            if self._event_bus:
                await self._event_bus._publish_internal(
                    EventType.WORKER_CRASHED,
                    {
                        "session_id": self.session_id,
                        "error": str(e),
                        "processed_count": self._processed_count,
                        "error_count": self._error_count
                    }
                )
        finally:
            self._running = False
            self._logger.debug(f"Worker завершён (обработано: {self._processed_count}, ошибок: {self._error_count})")

    async def _process_event(self, event: Event):
        """Обработка одного события."""
        self._sequence_counter += 1
        event.sequence_number = self._sequence_counter
        self._processed_count += 1

        # Получаем подписчиков для этого типа события
        event_type_handlers = self._subscribers.get(event.event_type, [])
        all_handlers = self._all_subscribers[:]

        # Фильтруем подписчиков по domain и session_id
        handlers_to_call = []

        for sub_info in event_type_handlers:
            if sub_info.matches(event):
                handlers_to_call.append(sub_info.handler)

        for sub_info in all_handlers:
            if sub_info.matches(event):
                handlers_to_call.append(sub_info.handler)

        if not handlers_to_call:
            return

        # Вызываем подписчиков последовательно (FIFO)
        for handler in handlers_to_call:
            try:
                await self._call_subscriber(handler, event)
            except Exception as e:
                self._logger.error(f"Ошибка в подписчике {handler.__name__}: {e}", exc_info=True)
                self._error_count += 1

                if self._event_bus:
                    await self._event_bus._publish_internal(
                        EventType.SUBSCRIBER_FAILED,
                        {
                            "session_id": self.session_id,
                            "subscriber": handler.__name__,
                            "event_type": event.event_type,
                            "error": str(e)
                        }
                    )

    async def _call_subscriber(self, handler: Callable, event: Event):
        """Вызов подписчика с таймаутом."""
        try:
            if inspect.iscoroutinefunction(handler):
                await asyncio.wait_for(handler(event), timeout=self._subscriber_timeout)
            else:
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, handler, event),
                    timeout=self._subscriber_timeout
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Subscriber {handler.__name__} превысил таймаут ({self._subscriber_timeout}s)")

    async def stop(self):
        """Остановка worker'а."""
        self._logger.debug("Остановка worker'а...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._logger.debug("Worker остановлен")

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


# =============================================================================
# UNIFIED EVENT BUS
# =============================================================================

class UnifiedEventBus:
    """
    Единая шина событий с поддержкой session isolation и domain routing.

    ARCHITECTURE:
    - publish() кладёт событие в session_queue
    - SessionWorker читает из очереди и sequentially вызывает subscribers
    - Порядок внутри сессии гарантирован (FIFO)
    - Между сессиями — параллельность
    - Domain routing внутри одной шины

    FEATURES:
    - ✅ Session isolation — события сессии A не видны сессии B
    - ✅ Domain routing — подписка на события конкретных доменов
    - ✅ FIFO порядок внутри сессии
    - ✅ Backpressure — ограничение размера очереди
    - ✅ No event duplication — событие не дублируется между шинами
    - ✅ Backward compatibility — поддержка старого API

    USAGE:
    ```python
    # Базовое использование
    event_bus = get_event_bus()

    # Подписка на событие
    event_bus.subscribe(EventType.AGENT_STARTED, handler)

    # Подписка с фильтром по домену
    event_bus.subscribe(
        EventType.AGENT_STARTED,
        handler,
        domain=EventDomain.AGENT
    )

    # Подписка с фильтром по сессии
    event_bus.subscribe(
        EventType.AGENT_STARTED,
        handler,
        session_id="session_123"
    )

    # Глобальная подписка с фильтром по доменам
    event_bus.subscribe_all(
        handler,
        domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE]
    )

    # Публикация события
    await event_bus.publish(
        EventType.AGENT_STARTED,
        data={"agent_id": "123"},
        session_id="session_123",
        domain=EventDomain.AGENT
    )
    ```
    """

    def __init__(
        self,
        queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
        worker_idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
        subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT
    ):
        # Подписчики с метаданными
        self._subscribers: Dict[str, List[SubscriberInfo]] = {}
        self._all_subscribers: List[SubscriberInfo] = []

        # Сессии и очереди
        self._session_queues: Dict[str, asyncio.Queue] = {}
        self._session_workers: Dict[str, SessionWorker] = {}
        self._active_sessions: Dict[str, SessionMeta] = {}

        # Настройки
        self._queue_max_size = queue_max_size
        self._worker_idle_timeout = worker_idle_timeout
        self._subscriber_timeout = subscriber_timeout

        # Состояние
        self._running = True
        self._shutdown_event = asyncio.Event()

        # Внутренний логгер
        self._internal_logger = logging.getLogger(f"{__name__}.UnifiedEventBus")

        # Блокировка для потокобезопасного создания workers
        self._lock = asyncio.Lock()

        # === МИГРАЦИЯ: счётчик дублирования подписчиков ===
        self._duplicate_subscription_count = 0
        self._duplicate_event_warning_threshold = 10  # Предупреждение после N дубликатов

    # =========================================================================
    # ПОДПИСКА / ОТПИСКА
    # =========================================================================

    def subscribe(
        self,
        event_type: Union[str, EventType],
        handler: Callable,
        domain: Optional[EventDomain] = None,
        session_id: Optional[str] = None
    ):
        """
        Подписка на событие с фильтрацией по домену и сессии.

        ARGS:
        - event_type: тип события (EventType или строка)
        - handler: функция-обработчик (async или sync)
        - domain: фильтр по домену (опционально)
        - session_id: фильтр по сессии (опционально)

        EXAMPLE:
        ```python
        # Подписка на все события AGENT_STARTED
        event_bus.subscribe(EventType.AGENT_STARTED, handler)

        # Подписка только на AGENT события
        event_bus.subscribe(
            EventType.AGENT_STARTED,
            handler,
            domain=EventDomain.AGENT
        )

        # Подписка только для конкретной сессии
        event_bus.subscribe(
            EventType.AGENT_STARTED,
            handler,
            session_id="session_123"
        )
        ```
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str not in self._subscribers:
            self._subscribers[event_type_str] = []

        sub_info = SubscriberInfo(
            handler=handler,
            domain=domain,
            session_id=session_id
        )

        # === МИГРАЦИЯ: детекция дублирования подписчиков ===
        for existing_sub in self._subscribers[event_type_str]:
            if existing_sub.handler == handler:
                # Обнаружено дублирование подписки!
                self._duplicate_subscription_count += 1
                if self._duplicate_subscription_count <= self._duplicate_event_warning_threshold:
                    self._internal_logger.warning(
                        f"⚠️ MIGRATION: Обнаружено дублирование подписчика на {event_type_str}: "
                        f"{handler.__name__} (domain={domain}, session_id={session_id}). "
                        f"Всего дубликатов: {self._duplicate_subscription_count}"
                    )
                elif self._duplicate_subscription_count == self._duplicate_event_warning_threshold + 1:
                    self._internal_logger.warning(
                        f"⚠️ MIGRATION: Слишком много дубликатов подписчиков ({self._duplicate_subscription_count}). "
                        f"Дальнейшие предупреждения отключены."
                    )
                return  # Не добавляем дубликат

        if sub_info not in self._subscribers[event_type_str]:
            self._subscribers[event_type_str].append(sub_info)
            self._internal_logger.debug(
                f"Подписан обработчик на {event_type_str}: {handler.__name__}, "
                f"domain={domain}, session_id={session_id}"
            )

    def subscribe_all(
        self,
        handler: Callable,
        domains: Optional[List[EventDomain]] = None
    ):
        """
        Подписка на все события с фильтрацией по доменам.

        ARGS:
        - handler: функция-обработчик (async или sync)
        - domains: список доменов для фильтрации (опционально)

        EXAMPLE:
        ```python
        # Подписка на все события
        event_bus.subscribe_all(handler)

        # Подписка только на AGENT и INFRASTRUCTURE события
        event_bus.subscribe_all(
            handler,
            domains=[EventDomain.AGENT, EventDomain.INFRASTRUCTURE]
        )
        ```
        """
        sub_info = SubscriberInfo(
            handler=handler,
            domains=domains
        )

        if sub_info not in self._all_subscribers:
            self._all_subscribers.append(sub_info)
            self._internal_logger.debug(
                f"Подписан обработчик на все события: {handler.__name__}, "
                f"domains={domains}"
            )

    def unsubscribe(
        self,
        event_type: Union[str, EventType],
        handler: Callable
    ):
        """
        Отписка от события.

        ARGS:
        - event_type: тип события (EventType или строка)
        - handler: функция-обработчик
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str in self._subscribers:
            self._subscribers[event_type_str] = [
                sub for sub in self._subscribers[event_type_str]
                if sub.handler != handler
            ]

    def unsubscribe_all(self, handler: Callable):
        """Отписка от всех событий."""
        self._all_subscribers = [
            sub for sub in self._all_subscribers
            if sub.handler != handler
        ]

        for event_type in list(self._subscribers.keys()):
            self._subscribers[event_type] = [
                sub for sub in self._subscribers[event_type]
                if sub.handler != handler
            ]

    # =========================================================================
    # ПУБЛИКАЦИЯ СОБЫТИЙ
    # =========================================================================

    async def publish(
        self,
        event_type: Union[Event, str, EventType] = None,
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
        session_id: str = "",
        agent_id: str = "",
        correlation_id: str = "",
        domain: Optional[EventDomain] = None,
        # Для обратной совместимости
        event: Union[Event, str, EventType, None] = None
    ):
        """
        Публикация события с domain routing.

        ВАЖНО:
        - НЕ await subscriber напрямую
        - Кладёт событие в session_queue
        - Создаёт worker если не существует

        ARGS:
        - event_type: тип события или Event объект
        - data: данные события
        - source: источник
        - session_id: ID сессии (обязательно для маршрутизации)
        - agent_id: ID агента
        - correlation_id: идентификатор корреляции
        - domain: домен события (опционально, определяется автоматически)
        - event: альтернативный параметр для обратной совместимости

        RETURNS:
        - bool: True если событие опубликовано успешно
        """
        # Обратная совместимость: если передан event= вместо event_type=
        if event_type is None and event is not None:
            event_type = event

        if event_type is None:
            self._internal_logger.warning("publish() вызван без event_type")
            return False

        if not self._running:
            self._internal_logger.warning("EventBus остановлен, событие отклонено")
            return False

        # Создаём Event объект
        event_obj = self._create_event(
            event_type, data, source, session_id, agent_id, correlation_id, domain
        )

        # Гарантируем наличие session_id
        if not event_obj.session_id:
            # Используем единую системную сессию для всех событий без session_id
            event_obj.session_id = SYSTEM_SESSION_ID
            # Убрал логирование чтобы избежать цикла с LoggingToEventBusHandler
            # self._internal_logger.debug(f"Использована системная сессия для события: {event_obj.event_type}")

        # Получаем или создаём очередь для сессии
        queue = await self._get_or_create_queue(event_obj.session_id, event_obj.agent_id)

        # BackPressure — проверка размера очереди
        if queue.qsize() >= self._queue_max_size:
            # Убрал публикацию события QUEUE_OVERFLOW чтобы избежать цикла
            # Просто предупреждение в internal logger
            self._internal_logger.warning(
                f"Queue overflow для сессии {event_obj.session_id}: {queue.qsize}/{self._queue_max_size} (событие не публикуется)"
            )
            # Пропускаем событие чтобы не перегружать очередь
            return False

        await queue.put(event_obj)
        return True

    def publish_sync(
        self,
        event_type: Union[Event, str, EventType] = None,
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
        session_id: str = "",
        agent_id: str = "",
        correlation_id: str = "",
        domain: Optional[EventDomain] = None,
        # Для обратной совместимости
        event: Union[Event, str, EventType, None] = None
    ) -> bool:
        """
        Синхронная публикация события (без await).

        ВАЖНО:
        - Должна вызываться только из того же потока, где работает asyncio цикл
        - Если worker для сессии ещё не создан, используется fallback (internal logger)
        - События помещаются в очередь через put_nowait (FIFO порядок сохраняется)

        ARGS:
        - event_type: тип события или Event объект
        - data: данные события
        - source: источник
        - session_id: ID сессии (обязательно для маршрутизации)
        - agent_id: ID агента
        - correlation_id: идентификатор корреляции
        - domain: домен события (опционально, определяется автоматически)
        - event: альтернативный параметр для обратной совместимости

        RETURNS:
        - bool: True если событие опубликовано успешно, False если отклонено
        """
        # Обратная совместимость: если передан event= вместо event_type=
        if event_type is None and event is not None:
            event_type = event

        if event_type is None:
            self._internal_logger.warning("publish_sync() вызван без event_type")
            return False

        if not self._running:
            self._internal_logger.warning("EventBus остановлен, событие отклонено")
            return False

        # Создаём Event объект
        event_obj = self._create_event(
            event_type, data, source, session_id, agent_id, correlation_id, domain
        )

        # Гарантируем наличие session_id
        if not event_obj.session_id:
            event_obj.session_id = SYSTEM_SESSION_ID

        # Проверяем наличие очереди (синхронно, без await)
        queue = self._session_queues.get(event_obj.session_id)

        # Если очереди нет — worker ещё не создан, используем fallback
        if queue is None:
            self._internal_logger.warning(
                f"Синхронная публикация до создания worker для сессии {event_obj.session_id}, "
                f"событие отклонено (используйте стандартный логгер в конструкторах)"
            )
            return False

        # BackPressure — проверка размера очереди
        if queue.qsize() >= self._queue_max_size:
            self._internal_logger.warning(
                f"Queue overflow для сессии {event_obj.session_id}: {queue.qsize}/{self._queue_max_size} (событие отклонено)"
            )
            return False

        # Помещаем событие в очередь синхронно
        try:
            queue.put_nowait(event_obj)
            return True
        except asyncio.QueueFull:
            self._internal_logger.warning(
                f"Queue full для сессии {event_obj.session_id}, событие отклонено"
            )
            return False

    def _create_event(
        self,
        event_type: Union[Event, str, EventType],
        data: Optional[Dict[str, Any]],
        source: str,
        session_id: str,
        agent_id: str,
        correlation_id: str,
        domain: Optional[EventDomain]
    ) -> Event:
        """Создание Event объекта."""
        if isinstance(event_type, Event):
            event = event_type
            if session_id:
                event.session_id = session_id
            if agent_id:
                event.agent_id = agent_id
            if correlation_id:
                event.correlation_id = correlation_id
            if domain:
                event.domain = domain
            return event

        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        # Определение домена
        if domain is None:
            domain = get_event_domain(event_type_str)

        return Event(
            event_type=event_type_str,
            data=data or {},
            source=source,
            session_id=session_id,
            agent_id=agent_id,
            correlation_id=correlation_id,
            domain=domain
        )

    async def _get_or_create_queue(
        self,
        session_id: str,
        agent_id: str
    ) -> asyncio.Queue:
        """Получение или создание очереди для сессии."""
        async with self._lock:
            if session_id not in self._session_queues:
                queue = asyncio.Queue(maxsize=0)
                self._session_queues[session_id] = queue

                self._active_sessions[session_id] = SessionMeta(
                    session_id=session_id,
                    agent_id=agent_id,
                    created_at=datetime.now(),
                    last_event_at=datetime.now()
                )

                worker = SessionWorker(
                    session_id=session_id,
                    agent_id=agent_id,
                    queue=queue,
                    subscribers=self._subscribers,
                    all_subscribers=self._all_subscribers,
                    idle_timeout=self._worker_idle_timeout,
                    subscriber_timeout=self._subscriber_timeout,
                    event_bus=self,
                    session_bound=True  # ← Worker живёт пока сессия активна
                )
                self._session_workers[session_id] = worker

                await worker.start()

                # Логирование с указанием типа сессии
                if agent_id:
                    self._internal_logger.info(
                        f"Создана сессия {session_id} (agent={agent_id})"
                    )
                else:
                    self._internal_logger.info(
                        f"Создана системная сессия {session_id}"
                    )

                await self._publish_internal(
                    EventType.SESSION_CREATED,
                    {
                        "session_id": session_id,
                        "agent_id": agent_id
                    }
                )

            if session_id in self._active_sessions:
                self._active_sessions[session_id].last_event_at = datetime.now()
                self._active_sessions[session_id].event_count += 1

            return self._session_queues[session_id]

    async def _publish_internal(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        session_id: str = "system"
    ):
        """
        Внутренняя публикация телеметрических событий.

        Эти события не проходят через обычную очередь чтобы избежать рекурсии.
        """
        event = Event(
            event_type=event_type.value,
            data=data,
            session_id=session_id,
            source="event_bus"
        )

        handlers = [sub.handler for sub in self._all_subscribers[:]]

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
            except Exception as e:
                self._internal_logger.error(f"Ошибка в internal handler: {e}")

    # =========================================================================
    # УПРАВЛЕНИЕ СЕССИЯМИ
    # =========================================================================

    async def close_session(self, session_id: str, wait_empty: bool = True):
        """
        Закрытие сессии.

        ARGS:
        - session_id: ID сессии
        - wait_empty: ждать опустошения очереди
        """
        if session_id not in self._session_workers:
            self._internal_logger.debug(f"Сессия {session_id} не найдена")
            return

        worker = self._session_workers[session_id]
        queue = self._session_queues[session_id]

        if wait_empty and not queue.empty():
            await queue.join()

        await worker.stop()

        del self._session_workers[session_id]
        del self._session_queues[session_id]

        if session_id in self._active_sessions:
            self._active_sessions[session_id].is_active = False

        self._internal_logger.debug(f"Сессия {session_id} закрыта")

        await self._publish_internal(
            EventType.WORKER_CLOSED,
            {
                "session_id": session_id,
                "processed_count": worker.processed_count,
                "error_count": worker.error_count
            }
        )

    async def close_all_sessions(self, wait_empty: bool = True):
        """Закрытие всех сессий."""
        session_ids = list(self._session_workers.keys())
        self._internal_logger.info(f"Закрытие {len(session_ids)} сессий")

        tasks = [
            self.close_session(session_id, wait_empty)
            for session_id in session_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    # =========================================================================
    # SHUTDOWN
    # =========================================================================

    async def shutdown(self, timeout: float = 30.0):
        """
        Корректное завершение работы EventBus.

        1. Останавливает приём новых событий
        2. Ждёт опустошения всех очередей
        3. Завершает worker'ы
        4. Закрывает подписчиков

        ARGS:
        - timeout: максимальное время ожидания
        """
        self._internal_logger.info("Начало shutdown EventBus")
        self._running = False

        try:
            self._internal_logger.debug("Ожидание опустошения очередей...")

            async def wait_queues():
                tasks = [
                    queue.join() for queue in self._session_queues.values()
                    if not queue.empty()
                ]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.wait_for(wait_queues(), timeout=timeout / 2)

            await self.close_all_sessions(wait_empty=False)

            self._internal_logger.info("EventBus shutdown завершён")

        except asyncio.TimeoutError:
            self._internal_logger.warning(
                f"Shutdown timeout ({timeout}s), принудительное завершение"
            )
            for worker in list(self._session_workers.values()):
                await worker.stop()

        except Exception as e:
            self._internal_logger.error(f"Ошибка при shutdown: {e}", exc_info=True)
            raise

        finally:
            self._shutdown_event.set()

    # =========================================================================
    # СТАТИСТИКА
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики EventBus."""
        return {
            "running": self._running,
            "active_sessions": len(self._active_sessions),
            "active_workers": len(
                [w for w in self._session_workers.values() if w.is_running]
            ),
            "total_queues": len(self._session_queues),
            "subscribers_count": sum(
                len(handlers) for handlers in self._subscribers.values()
            ),
            "all_subscribers_count": len(self._all_subscribers),
            # === МИГРАЦИЯ: статистика дублирования ===
            "duplicate_subscription_count": self._duplicate_subscription_count,
            "sessions": {
                session_id: {
                    "agent_id": meta.agent_id,
                    "event_count": meta.event_count,
                    "sequence_counter": meta.sequence_counter,
                    "is_active": meta.is_active,
                    "queue_size": (
                        self._session_queues.get(session_id, None).qsize()
                        if session_id in self._session_queues else 0
                    ),
                    "worker_running": (
                        self._session_workers.get(session_id, None).is_running
                        if session_id in self._session_workers else False
                    ),
                    "processed_count": (
                        self._session_workers.get(session_id, None).processed_count
                        if session_id in self._session_workers else 0
                    ),
                    "error_count": (
                        self._session_workers.get(session_id, None).error_count
                        if session_id in self._session_workers else 0
                    ),
                }
                for session_id, meta in self._active_sessions.items()
            }
        }

    def get_session_meta(self, session_id: str) -> Optional[SessionMeta]:
        """Получение метаданных сессии."""
        return self._active_sessions.get(session_id)

    def get_active_sessions(self) -> List[str]:
        """Получение списка активных session_id."""
        return [
            session_id for session_id, meta in self._active_sessions.items()
            if meta.is_active
        ]

    def get_sessions_by_agent(self, agent_id: str) -> List[str]:
        """Получение session_id для конкретного агента."""
        return [
            session_id for session_id, meta in self._active_sessions.items()
            if meta.agent_id == agent_id
        ]

    # =========================================================================
    # МИГРАЦИЯ: статистика дублирования
    # =========================================================================

    def get_migration_stats(self) -> Dict[str, Any]:
        """
        Получение статистики миграции.

        ВОЗВРАЩАЕТ:
        - duplicate_subscription_count: количество обнаруженных дубликатов подписчиков
        - duplicate_warning_threshold: порог предупреждений
        - migration_active: True если идёт миграция
        """
        return {
            "duplicate_subscription_count": self._duplicate_subscription_count,
            "duplicate_warning_threshold": self._duplicate_event_warning_threshold,
            "migration_active": True,
            "message": "Статистика миграции: отслеживание дублирования подписчиков"
        }

    def reset_migration_stats(self):
        """Сброс статистики миграции."""
        self._duplicate_subscription_count = 0
        self._internal_logger.info("Статистика миграции сброшена")


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

_global_event_bus: Optional[UnifiedEventBus] = None


def get_event_bus() -> UnifiedEventBus:
    """
    Получение глобального UnifiedEventBus (singleton).

    RETURNS:
    - глобальный экземпляр UnifiedEventBus
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = UnifiedEventBus()
    return _global_event_bus


def create_event_bus(
    queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
    worker_idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
    subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT
) -> UnifiedEventBus:
    """
    Создание нового UnifiedEventBus (для тестов или изолированных контекстов).

    ARGS:
    - queue_max_size: максимальный размер очереди
    - worker_idle_timeout: таймаут простоя worker'а
    - subscriber_timeout: таймаут выполнения подписчика

    RETURNS:
    - новый экземпляр UnifiedEventBus
    """
    return UnifiedEventBus(
        queue_max_size=queue_max_size,
        worker_idle_timeout=worker_idle_timeout,
        subscriber_timeout=subscriber_timeout
    )


async def shutdown_event_bus(timeout: float = 30.0):
    """
    Корректное завершение работы глобального UnifiedEventBus.

    ARGS:
    - timeout: максимальное время ожидания
    """
    global _global_event_bus
    if _global_event_bus:
        await _global_event_bus.shutdown(timeout=timeout)
        _global_event_bus = None
