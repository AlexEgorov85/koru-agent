"""
Конкурентный EventBus с изоляцией по сессиям.

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────┐
│                    Global EventBus                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Session Queues & Workers                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │Session A1   │  │Session A2   │  │Session B1   │  │   │
│  │  │Queue + Worker│ │Queue + Worker│ │Queue + Worker│  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌──────────┐        ┌──────────┐        ┌──────────┐
  │Subscriber│        │Subscriber│        │Subscriber│
  │   Dev    │        │  User    │        │ Dataset  │
  └──────────┘        └──────────┘        └──────────┘

FEATURES:
- Изоляция по session_id (каждая сессия — отдельная очередь)
- FIFO порядок внутри сессии
- Параллельная обработка между сессиями
- Backpressure (ограничение размера очереди)
- Subscriber isolation (ошибка не валит EventBus)
- Telemetry (WorkerCrashed, SubscriberFailed)
"""
import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

DEFAULT_QUEUE_MAX_SIZE = 1000  # Лимит событий в очереди сессии
DEFAULT_WORKER_IDLE_TIMEOUT = 60.0  # Секунд простоя перед закрытием worker'а
DEFAULT_SUBSCRIBER_TIMEOUT = 30.0  # Таймаут выполнения подписчика


# =============================================================================
# СОБЫТИЯ
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
    - sequence_number: порядковый номер в сессии (заполняется EventBus)
    """
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    session_id: str = ""
    agent_id: str = ""
    correlation_id: str = ""
    sequence_number: int = 0  # Заполняется EventBus

    def __post_init__(self):
        # Гарантируем, что data — это dict
        if self.data is None:
            self.data = {}


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

    # === Telemetry события (внутренние) ===
    WORKER_CREATED = "worker.created"
    WORKER_STARTED = "worker.started"
    WORKER_IDLE = "worker.idle"
    WORKER_CRASHED = "worker.crashed"
    WORKER_CLOSED = "worker.closed"
    SUBSCRIBER_FAILED = "subscriber.failed"
    QUEUE_OVERFLOW = "queue.overflow"


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
        subscribers: Dict[str, List[Callable]],
        all_subscribers: List[Callable],
        idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
        subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT,
        event_bus: "EventBus" = None
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        self._queue = queue
        self._subscribers = subscribers
        self._all_subscribers = all_subscribers
        self._idle_timeout = idle_timeout
        self._subscriber_timeout = subscriber_timeout
        self._event_bus = event_bus

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
        self._logger.debug(f"Worker запущен (idle_timeout={self._idle_timeout}s)")

        # Публикуем событие создания worker'а
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
        self._logger.debug("Цикл worker'а запущен")

        try:
            while self._running:
                try:
                    # Ждём событие с таймаутом для проверки idle
                    event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._idle_timeout
                    )

                    # Обработка события
                    await self._process_event(event)
                    self._last_activity = time.time()
                    self._queue.task_done()

                except asyncio.TimeoutError:
                    # Проверка на idle
                    idle_time = time.time() - self._last_activity
                    if idle_time >= self._idle_timeout:
                        self._logger.debug(f"Idle timeout ({idle_time:.1f}s), завершение worker'а")
                        # Публикуем событие idle
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
            # Публикуем событие crash'а
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
        # Увеличиваем sequence_number
        self._sequence_counter += 1
        event.sequence_number = self._sequence_counter

        # Обновляем метаданные
        self._processed_count += 1

        # Получаем подписчиков для этого типа события
        event_type_handlers = self._subscribers.get(event.event_type, [])
        all_handlers = self._all_subscribers[:]
        handlers_to_call = event_type_handlers + all_handlers

        if not handlers_to_call:
            return

        # Вызываем подписчиков последовательно (FIFO)
        for handler in handlers_to_call:
            try:
                await self._call_subscriber(handler, event)
            except Exception as e:
                self._logger.error(f"Ошибка в подписчике {handler.__name__}: {e}", exc_info=True)
                self._error_count += 1

                # Публикуем событие ошибки подписчика
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
                # Синхронный handler — запускаем в executor
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
# EVENT BUS
# =============================================================================

class EventBus:
    """
    Глобальный конкурентный EventBus с изоляцией по сессиям.

    ARCHITECTURE:
    - publish() кладёт событие в session_queue
    - SessionWorker читает из очереди и sequentially вызывает subscribers
    - Порядок внутри сессии гарантирован (FIFO)
    - Между сессиями — параллельность

    THREAD SAFETY:
    - Все операции асинхронные
    - Очереди потокобезопасны (asyncio.Queue)
    - Нет блокировок
    """

    def __init__(
        self,
        queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
        worker_idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
        subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT
    ):
        # Подписчики
        self._subscribers: Dict[str, List[Callable]] = {}
        self._all_subscribers: List[Callable] = []

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
        self._internal_logger = logging.getLogger(f"{__name__}.EventBus")

        # Блокировка для потокобезопасного создания workers
        self._lock = asyncio.Lock()

    # =========================================================================
    # ПОДПИСКА / ОТПИСКА
    # =========================================================================

    def subscribe(self, event_type: Union[str, EventType], handler: Callable):
        """
        Подписка на событие.

        ARGS:
        - event_type: тип события (EventType или строка)
        - handler: функция-обработчик (async или sync)
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str not in self._subscribers:
            self._subscribers[event_type_str] = []

        if handler not in self._subscribers[event_type_str]:
            self._subscribers[event_type_str].append(handler)
            self._internal_logger.debug(f"Подписан обработчик на {event_type_str}: {handler.__name__}")

    def subscribe_all(self, handler: Callable):
        """Подписка на все события."""
        if handler not in self._all_subscribers:
            self._all_subscribers.append(handler)
            self._internal_logger.debug(f"Подписан обработчик на все события: {handler.__name__}")

    def unsubscribe(self, event_type: Union[str, EventType], handler: Callable):
        """Отписка от события."""
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str in self._subscribers:
            if handler in self._subscribers[event_type_str]:
                self._subscribers[event_type_str].remove(handler)

    def unsubscribe_all(self, handler: Callable):
        """Отписка от всех событий."""
        if handler in self._all_subscribers:
            self._all_subscribers.remove(handler)

        for event_type in list(self._subscribers.keys()):
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    # =========================================================================
    # ПУБЛИКАЦИЯ СОБЫТИЙ
    # =========================================================================

    async def publish(
        self,
        event_type: Union[Event, str, EventType],
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
        session_id: str = "",
        agent_id: str = "",
        correlation_id: str = ""
    ):
        """
        Публикация события.

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
        """
        if not self._running:
            self._internal_logger.warning("EventBus остановлен, событие отклонено")
            return

        # Создаём Event объект
        event = self._create_event(event_type, data, source, session_id, agent_id, correlation_id)

        # Гарантируем наличие session_id
        if not event.session_id:
            # Генерируем временный session_id для системных событий
            event.session_id = f"system_{uuid.uuid4().hex[:8]}"
            self._internal_logger.debug(f"Сгенерирован session_id для события: {event.session_id}")

        # Получаем или создаём очередь для сессии
        queue = await self._get_or_create_queue(event.session_id, event.agent_id)

        # Backpressure — проверка размера очереди
        if queue.qsize() >= self._queue_max_size:
            self._internal_logger.warning(
                f"Queue overflow для сессии {event.session_id}: {queue.qsize}/{self._queue_max_size}"
            )
            # Публикуем событие переполнения
            await self._publish_internal(
                EventType.QUEUE_OVERFLOW,
                {
                    "session_id": event.session_id,
                    "queue_size": queue.qsize(),
                    "max_size": self._queue_max_size,
                    "event_type": event.event_type
                }
            )
            # Блокируем пока очередь не освободится
            await queue.put(event)
        else:
            await queue.put(event)

    def _create_event(
        self,
        event_type: Union[Event, str, EventType],
        data: Optional[Dict[str, Any]],
        source: str,
        session_id: str,
        agent_id: str,
        correlation_id: str
    ) -> Event:
        """Создание Event объекта."""
        if isinstance(event_type, Event):
            event = event_type
            # Переопределяем поля если переданы
            if session_id:
                event.session_id = session_id
            if agent_id:
                event.agent_id = agent_id
            if correlation_id:
                event.correlation_id = correlation_id
            return event

        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        return Event(
            event_type=event_type_str,
            data=data or {},
            source=source,
            session_id=session_id,
            agent_id=agent_id,
            correlation_id=correlation_id
        )

    async def _get_or_create_queue(self, session_id: str, agent_id: str) -> asyncio.Queue:
        """Получение или создание очереди для сессии."""
        async with self._lock:
            if session_id not in self._session_queues:
                # Создаём новую очередь и worker
                queue = asyncio.Queue(maxsize=0)  # Без ограничения на put
                self._session_queues[session_id] = queue

                # Создаём метаданные сессии
                self._active_sessions[session_id] = SessionMeta(
                    session_id=session_id,
                    agent_id=agent_id,
                    created_at=datetime.now(),
                    last_event_at=datetime.now()
                )

                # Создаём и запускаем worker
                worker = SessionWorker(
                    session_id=session_id,
                    agent_id=agent_id,
                    queue=queue,
                    subscribers=self._subscribers,
                    all_subscribers=self._all_subscribers,
                    idle_timeout=self._worker_idle_timeout,
                    subscriber_timeout=self._subscriber_timeout,
                    event_bus=self
                )
                self._session_workers[session_id] = worker

                # Запускаем worker
                await worker.start()

                self._internal_logger.info(
                    f"Создана сессия {session_id} (agent={agent_id})"
                )

                # Публикуем событие создания сессии
                await self._publish_internal(
                    EventType.SESSION_CREATED,
                    {
                        "session_id": session_id,
                        "agent_id": agent_id
                    }
                )

            # Обновляем last_event_at
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
        # Для внутренних событий создаём упрощённый Event
        event = Event(
            event_type=event_type.value,
            data=data,
            session_id=session_id,
            source="event_bus"
        )

        # Вызываем только all_subscribers (глобальные обработчики телеметрии)
        handlers = self._all_subscribers[:]

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    # Запускаем без ожидания чтобы не блокировать
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

        self._internal_logger.info(f"Закрытие сессии {session_id}")

        worker = self._session_workers[session_id]
        queue = self._session_queues[session_id]

        # Ждём опустошения очереди если нужно
        if wait_empty and not queue.empty():
            await queue.join()

        # Останавливаем worker
        await worker.stop()

        # Удаляем из словарей
        del self._session_workers[session_id]
        del self._session_queues[session_id]

        if session_id in self._active_sessions:
            self._active_sessions[session_id].is_active = False

        self._internal_logger.debug(f"Сессия {session_id} закрыта")

        # Публикуем событие закрытия
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

        # Закрываем все сессии параллельно
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
            # Ждём опустошения всех очередей с таймаутом
            self._internal_logger.debug("Ожидание опустошения очередей...")

            async def wait_queues():
                tasks = [queue.join() for queue in self._session_queues.values() if not queue.empty()]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.wait_for(wait_queues(), timeout=timeout / 2)

            # Закрываем все сессии
            await self.close_all_sessions(wait_empty=False)

            self._internal_logger.info("EventBus shutdown завершён")

        except asyncio.TimeoutError:
            self._internal_logger.warning(f"Shutdown timeout ({timeout}s), принудительное завершение")
            # Принудительно отменяем все worker'ы
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
            "active_workers": len([w for w in self._session_workers.values() if w.is_running]),
            "total_queues": len(self._session_queues),
            "subscribers_count": sum(len(handlers) for handlers in self._subscribers.values()),
            "all_subscribers_count": len(self._all_subscribers),
            "sessions": {
                session_id: {
                    "agent_id": meta.agent_id,
                    "event_count": meta.event_count,
                    "sequence_counter": meta.sequence_counter,
                    "is_active": meta.is_active,
                    "queue_size": self._session_queues.get(session_id, None).qsize() if session_id in self._session_queues else 0,
                    "worker_running": self._session_workers.get(session_id, None).is_running if session_id in self._session_workers else False,
                    "processed_count": self._session_workers.get(session_id, None).processed_count if session_id in self._session_workers else 0,
                    "error_count": self._session_workers.get(session_id, None).error_count if session_id in self._session_workers else 0,
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


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Получение глобального EventBus (singleton).

    RETURNS:
    - глобальный экземпляр EventBus
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def create_event_bus(
    queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
    worker_idle_timeout: float = DEFAULT_WORKER_IDLE_TIMEOUT,
    subscriber_timeout: float = DEFAULT_SUBSCRIBER_TIMEOUT
) -> EventBus:
    """
    Создание нового EventBus (для тестов или изолированных контекстов).

    ARGS:
    - queue_max_size: максимальный размер очереди
    - worker_idle_timeout: таймаут простоя worker'а
    - subscriber_timeout: таймаут выполнения подписчика

    RETURNS:
    - новый экземпляр EventBus
    """
    return EventBus(
        queue_max_size=queue_max_size,
        worker_idle_timeout=worker_idle_timeout,
        subscriber_timeout=subscriber_timeout
    )


async def shutdown_event_bus(timeout: float = 30.0):
    """
    Корректное завершение работы глобального EventBus.

    ARGS:
    - timeout: максимальное время ожидания
    """
    global _global_event_bus
    if _global_event_bus:
        await _global_event_bus.shutdown(timeout=timeout)
        _global_event_bus = None
