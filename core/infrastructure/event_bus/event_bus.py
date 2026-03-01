"""
Шина событий для системы агентов.
ОСОБЕННОСТИ:
- Асинхронная обработка событий
- Поддержка подписчиков на события
- Замена системы логирования
"""
import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Type, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Event:
    """
    Базовый класс события.
    
    ATTRIBUTES:
    - event_type: тип события
    - data: данные события
    - timestamp: время возникновения события
    - source: источник события
    - correlation_id: идентификатор корреляции для отслеживания цепочек событий
    """
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: str = ""


class EventType(Enum):
    """
    Типы событий в системе.
    """
    # События жизненного цикла системы
    SYSTEM_INITIALIZED = "system.initialized"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # События агента
    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # События выполнения
    CAPABILITY_SELECTED = "capability.selected"
    SKILL_EXECUTED = "skill.executed"
    ACTION_PERFORMED = "action.performed"
    STEP_REGISTERED = "step.registered"

    # События контекста
    CONTEXT_ITEM_ADDED = "context.item.added"
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"

    # События провайдеров
    PROVIDER_REGISTERED = "provider.registered"
    PROVIDER_UNREGISTERED = "provider.unregistered"
    LLM_CALL_STARTED = "llm.call.started"
    LLM_CALL_COMPLETED = "llm.call.completed"
    LLM_CALL_FAILED = "llm.call.failed"
    LLM_PROMPT_GENERATED = "llm.prompt.generated"  # Сгенерирован промпт для LLM
    LLM_RESPONSE_RECEIVED = "llm.response.received"  # Получен ответ от LLM

    # События сервисов
    SERVICE_REGISTERED = "services.registered"
    SERVICE_INITIALIZED = "services.initialized"
    SERVICE_SHUTDOWN = "services.shutdown"
    SERVICE_ERROR = "services.error"

    # События ошибок
    RETRY_ATTEMPT = "retry.attempt"
    ERROR_OCCURRED = "error.occurred"

    # События метрик
    METRIC_COLLECTED = "metric.collected"

    # События бенчмарков
    BENCHMARK_STARTED = "benchmark.started"
    BENCHMARK_COMPLETED = "benchmark.completed"
    BENCHMARK_FAILED = "benchmark.failed"

    # События оптимизации
    OPTIMIZATION_CYCLE_STARTED = "optimization.cycle.started"
    OPTIMIZATION_CYCLE_COMPLETED = "optimization.cycle.completed"
    OPTIMIZATION_FAILED = "optimization.failed"

    # События версий
    VERSION_PROMOTED = "version.promoted"
    VERSION_REJECTED = "version.rejected"
    VERSION_CREATED = "version.created"

    # События универсального логирования
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    COMPONENT_INITIALIZED = "component.initialized"
    COMPONENT_SHUTDOWN = "component.shutdown"
    
    # События логирования (заменяют logging.info)
    LOG_INFO = "log.info"
    LOG_DEBUG = "log.debug"
    LOG_WARNING = "log.warning"
    LOG_ERROR = "log.error"


class EventBus:
    """
    Асинхронная шина событий для системы агентов.
    
    FEATURES:
    - Поддержка асинхронных подписчиков
    - Фильтрация событий по типу
    - Поддержка корреляции событий
    - Безопасная обработка исключений в подписчиках
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._all_subscribers: List[Callable] = []
        
        # Настройка внутреннего логгера для отладки шины событий
        self._internal_logger = logging.getLogger(f"{__name__}.EventBus")
    
    def subscribe(self, event_type: Union[str, EventType], handler: Callable):
        """
        Подписка на событие.
        
        ARGS:
        - event_type: тип события (EventType или строка)
        - handler: функция-обработчик события
        
        EXAMPLE:
        ```python
        async def handle_agent_created(event: Event):
            print(f"Agent created: {event.data}")
            
        event_bus.subscribe(EventType.AGENT_CREATED, handle_agent_created)
        ```
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str not in self._subscribers:
            self._subscribers[event_type_str] = []

        # Проверка на дублирование подписчика
        if handler not in self._subscribers[event_type_str]:
            self._subscribers[event_type_str].append(handler)
            # self._internal_logger.debug(f"Подписан обработчик на событие: {event_type_str}")
        # else:
            # self._internal_logger.debug(f"Обработчик уже подписан на событие: {event_type_str}")
    
    def subscribe_all(self, handler: Callable):
        """
        Подписка на все события.
        
        ARGS:
        - handler: функция-обработчик события
        """
        self._all_subscribers.append(handler)
        self._internal_logger.debug("Подписан обработчик на все события")
    
    def unsubscribe(self, event_type: Union[str, EventType], handler: Callable):
        """
        Отписка от события.
        
        ARGS:
        - event_type: тип события (EventType или строка)
        - handler: функция-обработчик события
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        if event_type_str in self._subscribers:
            if handler in self._subscribers[event_type_str]:
                self._subscribers[event_type_str].remove(handler)
                self._internal_logger.debug(f"Отписан обработчик от события: {event_type_str}")
    
    async def publish(self, event: Union[Event, str, EventType], data: Dict[str, Any] = None, source: str = "", correlation_id: str = ""):
        """
        Публикация события.
        
        ARGS:
        - event: объект события, строка с типом события или EventType
        - data: данные события (если event - строка или EventType)
        - source: источник события
        - correlation_id: идентификатор корреляции
        
        RETURNS:
        - None
        """
        # Преобразование строки или EventType в объект события при необходимости
        if isinstance(event, (str, EventType)):
            event_type_str = event.value if isinstance(event, EventType) else event
            event_obj = Event(
                event_type=event_type_str,
                data=data or {},
                source=source,
                correlation_id=correlation_id
            )
        else:
            # Уже является объектом Event
            event_obj = event

        # Логирование публикации события (только для важных событий)
        if event_obj.event_type in ["error.occurred", "agent.started", "agent.completed"]:
            self._internal_logger.info(f"Публикация события: {event_obj.event_type} (источник: {event_obj.source})")

        # Получение списка подписчиков
        event_type_handlers = self._subscribers.get(event_obj.event_type, [])
        all_handlers = self._all_subscribers[:]
        
        # Асинхронная публикация события всем подписчикам
        handlers_to_call = event_type_handlers + all_handlers
        
        if not handlers_to_call:
            # Нет подписчиков на это событие
            return
        
        # Создание задач для асинхронного выполнения обработчиков
        tasks = []
        for handler in handlers_to_call:
            try:
                if inspect.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(event_obj))
                else:
                    # Обертка синхронной функции в асинхронную
                    task = asyncio.create_task(self._wrap_sync_handler(handler, event_obj))

                tasks.append(task)
            except Exception as e:
                self._internal_logger.error(f"Ошибка при создании задачи для обработчика: {e}")

        # Ожидание выполнения всех задач
        if tasks:
            try:
                # Запускаем все задачи асинхронно, но НЕ ждём их завершения
                # Это предотвращает блокировку при зависании одного из обработчиков
                for task in tasks:
                    # Добавляем обработчик ошибок для каждой задачи
                    task.add_done_callback(
                        lambda t: self._internal_logger.error(f"Ошибка в обработчике: {t.exception()}")
                        if t.exception() else None
                    )
            except Exception as e:
                self._internal_logger.error(f"Ошибка при запуске обработчиков события: {e}")
    
    async def _wrap_sync_handler(self, handler: Callable, event: Event):
        """
        Обертка синхронного обработчика для асинхронного вызова.
        
        ARGS:
        - handler: синхронная функция-обработчик
        - event: событие для обработки
        """
        try:
            handler(event)
        except Exception as e:
            self._internal_logger.error(f"Ошибка в синхронном обработчике события: {e}")
    
    def get_subscribers_count(self, event_type: Union[str, EventType]) -> int:
        """
        Получение количества подписчиков на событие.
        
        ARGS:
        - event_type: тип события
        
        RETURNS:
        - количество подписчиков
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        return len(self._subscribers.get(event_type_str, []))


# Глобальная шина событий (singleton)
_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """
    Получение глобальной шины событий.
    
    RETURNS:
    - глобальный экземпляр EventBus
    """
    return _global_event_bus