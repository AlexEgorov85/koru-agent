"""
Менеджер доменных шин событий.

АРХИТЕКТУРА:
- Разделение событий по доменам (agent, benchmark, infrastructure, optimization)
- Изоляция обработчиков между доменами
- Поддержка кросс-доменных событий
- Централизованное управление подписками

ПРЕИМУЩЕСТВА:
- ✅ Изоляция доменов — ошибки в одном домене не влияют на другие
- ✅ Легче отладка — понятен поток событий в каждом домене
- ✅ Можно отключать домены независимо
- ✅ Кросс-доменные события для интеграции
"""
import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from .event_bus import EventBus, Event, EventType


logger = logging.getLogger(__name__)


class EventDomain(Enum):
    """
    Домены событий для изоляции компонентов.
    """
    AGENT = "agent"           # События агента (планирование, выполнение, контекст)
    BENCHMARK = "benchmark"   # События бенчмарков (тесты, оптимизация)
    INFRASTRUCTURE = "infrastructure"  # Инфраструктурные события (провайдеры, сервисы)
    OPTIMIZATION = "optimization"  # События оптимизации (версии, эксперименты)
    SECURITY = "security"     # События безопасности (авторизация, аудит)
    COMMON = "common"         # Общие события (ошибки, метрики)


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
    
    # Common domain (по умолчанию)
    EventType.RETRY_ATTEMPT: EventDomain.COMMON,
    EventType.ERROR_OCCURRED: EventDomain.COMMON,
    EventType.METRIC_COLLECTED: EventDomain.COMMON,
    EventType.EXECUTION_STARTED: EventDomain.COMMON,
    EventType.EXECUTION_COMPLETED: EventDomain.COMMON,
    EventType.EXECUTION_FAILED: EventDomain.COMMON,
}


@dataclass
class DomainEvent(Event):
    """
    Событие с указанием домена.
    
    EXTENDS: Event
    ADDS:
    - domain: домен события
    """
    domain: EventDomain = EventDomain.COMMON
    
    @classmethod
    def from_event(cls, event: Event, domain: EventDomain = None) -> 'DomainEvent':
        """Создание DomainEvent из обычного Event."""
        if domain is None:
            # Автоматическое определение домена по типу события
            event_type = EventType(event.event_type) if event.event_type in [e.value for e in EventType] else None
            domain = EVENT_TYPE_TO_DOMAIN.get(event_type, EventDomain.COMMON) if event_type else EventDomain.COMMON
        
        return cls(
            event_type=event.event_type,
            data=event.data,
            timestamp=event.timestamp,
            source=event.source,
            correlation_id=event.correlation_id,
            domain=domain
        )


class DomainEventBus:
    """
    Доменная шина событий с поддержкой изоляции.
    
    FEATURES:
    - Изолированные подписчики для каждого домена
    - Статистика по событиям домена
    - Возможность включения/выключения домена
    """
    
    def __init__(self, domain: EventDomain, manager: 'EventBusManager' = None):
        self.domain = domain
        self._event_bus = EventBus()
        self._enabled = True
        self._event_count = 0
        self._error_count = 0
        self._manager = manager  # Ссылка на менеджер для глобальных подписчиков
        
        # Настройка логгера с указанием домена
        self._logger = logging.getLogger(f"{__name__}.{domain.value}")
    
    def subscribe(self, event_type: Union[str, EventType], handler: Callable):
        """Подписка на событие в рамках домена."""
        self._event_bus.subscribe(event_type, handler)
        self._self.event_bus_logger.debug(f"Подписан обработчик на {event_type}")
    
    def subscribe_all(self, handler: Callable):
        """Подписка на все события домена."""
        self._event_bus.subscribe_all(handler)
    
    def unsubscribe(self, event_type: Union[str, EventType], handler: Callable):
        """Отписка от события."""
        self._event_bus.unsubscribe(event_type, handler)
    
    async def publish(self, event: Union[Event, str, EventType], 
                     data: Dict[str, Any] = None, 
                     source: str = "", 
                     correlation_id: str = "") -> bool:
        """
        Публикация события в домене.
        
        RETURNS:
        - bool: True если событие опубликовано успешно
        """
        if not self._enabled:
            self._self.event_bus_logger.debug(f"Домен {self.domain.value} отключен, событие не опубликовано")
            return False
        
        try:
            # Преобразование в DomainEvent если нужно
            if isinstance(event, Event) and not isinstance(event, DomainEvent):
                event = DomainEvent.from_event(event, self.domain)
            elif isinstance(event, (str, EventType)):
                event_type_str = event.value if isinstance(event, EventType) else event
                event = DomainEvent(
                    event_type=event_type_str,
                    data=data or {},
                    source=source,
                    correlation_id=correlation_id,
                    domain=self.domain
                )
            
            await self._event_bus.publish(event)
            self._event_count += 1
            
            # Уведомление глобальных подписчиков через менеджер
            if self._manager and self._manager._global_subscribers:
                for handler in self._manager._global_subscribers:
                    try:
                        if inspect.iscoroutinefunction(handler):
                            asyncio.create_task(handler(event))
                        else:
                            handler(event)
                    except Exception as e:
                        self._self.event_bus_logger.error(f"Ошибка в глобальном подписчике: {e}")
            
            return True
            
        except Exception as e:
            self._error_count += 1
            self._self.event_bus_logger.error(f"Ошибка публикации события: {e}")
            return False
    
    def enable(self):
        """Включение домена."""
        self._enabled = True
        self._self.event_bus_logger.info(f"Домен {self.domain.value} включен")
    
    def disable(self):
        """Выключение домена."""
        self._enabled = False
        self._self.event_bus_logger.info(f"Домен {self.domain.value} выключен")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики по домену."""
        return {
            "domain": self.domain.value,
            "enabled": self._enabled,
            "event_count": self._event_count,
            "error_count": self._error_count,
            "subscribers_count": sum(
                self._event_bus.get_subscribers_count(event_type)
                for event_type in EventType
            )
        }


class EventBusManager:
    """
    Менеджер доменных шин событий.
    
    FEATURES:
    - Централизованное управление доменными шинами
    - Поддержка кросс-доменных событий
    - Глобальная подписка на все события
    - Статистика по всем доменам
    
    USAGE:
    ```python
    # Создание менеджера
    event_bus_manager = EventBusManager()
    
    # Получение шины конкретного домена
    agent_bus = event_bus_manager.get_bus(EventDomain.AGENT)
    agent_bus.subscribe(EventType.AGENT_CREATED, handler)
    
    # Публикация в домен
    await agent_bus.publish(EventType.AGENT_STARTED, {"agent_id": "123"})
    
    # Кросс-доменная публикация
    await event_bus_manager.publish_cross_domain(
        EventType.SYSTEM_INITIALIZED,
        domains=[EventDomain.INFRASTRUCTURE, EventDomain.AGENT]
    )
    
    # Подписка на все события
    event_bus_manager.subscribe_all(global_handler)
    ```
    """
    
    def __init__(self, domains: Optional[List[EventDomain]] = None):
        """
        Инициализация менеджера шин событий.
        
        ARGS:
        - domains: список доменов для создания (по умолчанию все стандартные)
        """
        self._domains = domains or list(EventDomain)
        self._buses: Dict[EventDomain, DomainEventBus] = {}
        self._global_subscribers: List[Callable] = []
        self._cross_domain_listeners: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger(__name__)
        
        # Инициализация шин для каждого домена
        for domain in self._domains:
            self._buses[domain] = DomainEventBus(domain, self)  # Передаем ссылку на менеджер
            self._self.event_bus_logger.debug(f"Создана шина для домена {domain.value}")
        
        self._self.event_bus_logger.info(f"EventBusManager инициализирован с {len(self._domains)} доменами")
    
    def get_bus(self, domain: Union[EventDomain, str]) -> DomainEventBus:
        """
        Получение шины конкретного домена.
        
        ARGS:
        - domain: домен (EventDomain или строка)
        
        RETURNS:
        - DomainEventBus: шина событий домена
        
        RAISES:
        - ValueError: если домен не найден
        """
        if isinstance(domain, str):
            try:
                domain = EventDomain(domain)
            except ValueError:
                raise ValueError(f"Неизвестный домен: {domain}. Доступные: {[d.value for d in EventDomain]}")
        
        if domain not in self._buses:
            raise ValueError(f"Домен {domain.value} не найден")
        
        return self._buses[domain]
    
    async def publish(self, event: Union[Event, str, EventType],
                     data: Dict[str, Any] = None,
                     source: str = "",
                     correlation_id: str = "",
                     domain: Optional[EventDomain] = None) -> bool:
        """
        Публикация события в шину домена.
        
        ARGS:
        - event: событие для публикации
        - data: данные события (если event — строка или EventType)
        - source: источник события
        - correlation_id: идентификатор корреляции
        - domain: целевой домен (опционально, определяется автоматически)
        
        RETURNS:
        - bool: True если событие опубликовано успешно
        """
        # Определение домена
        if domain is None:
            if isinstance(event, DomainEvent):
                domain = event.domain
            elif isinstance(event, Event):
                event_type = EventType(event.event_type) if event.event_type in [e.value for e in EventType] else None
                domain = EVENT_TYPE_TO_DOMAIN.get(event_type, EventDomain.COMMON) if event_type else EventDomain.COMMON
            elif isinstance(event, EventType):
                domain = EVENT_TYPE_TO_DOMAIN.get(event, EventDomain.COMMON)
            else:
                domain = EventDomain.COMMON
        
        # Публикация в шину домена
        bus = self.get_bus(domain)
        result = await bus.publish(event, data, source, correlation_id)
        
        # Уведомление глобальных подписчиков
        if result and self._global_subscribers:
            domain_event = DomainEvent.from_event(
                Event(
                    event_type=event.value if isinstance(event, EventType) else str(event),
                    data=data or {},
                    source=source,
                    correlation_id=correlation_id
                ),
                domain
            )
            for handler in self._global_subscribers:
                try:
                    if inspect.iscoroutinefunction(handler):
                        asyncio.create_task(handler(domain_event))
                    else:
                        handler(domain_event)
                except Exception as e:
                    self._self.event_bus_logger.error(f"Ошибка в глобальном подписчике: {e}")
        
        return result
    
    async def publish_cross_domain(self, event: Union[Event, str, EventType],
                                   domains: List[Union[EventDomain, str]],
                                   data: Dict[str, Any] = None,
                                   source: str = "",
                                   correlation_id: str = "") -> Dict[str, bool]:
        """
        Публикация события в несколько доменов одновременно.
        
        ARGS:
        - event: событие для публикации
        - domains: список целевых доменов
        - data: данные события
        - source: источник события
        - correlation_id: идентификатор корреляции
        
        RETURNS:
        - Dict[str, bool]: результат публикации по каждому домену
        """
        results = {}
        
        for domain in domains:
            try:
                result = await self.publish(event, data, source, correlation_id, domain)
                domain_name = domain.value if isinstance(domain, EventDomain) else domain
                results[domain_name] = result
            except Exception as e:
                domain_name = domain.value if isinstance(domain, EventDomain) else domain
                results[domain_name] = False
                self._self.event_bus_logger.error(f"Ошибка публикации в домен {domain_name}: {e}")
        
        return results
    
    def subscribe_all(self, handler: Callable):
        """
        Подписка на все события во всех доменах.
        
        ARGS:
        - handler: обработчик событий
        """
        self._global_subscribers.append(handler)
        self._self.event_bus_logger.debug("Зарегистрирован глобальный подписчик на все события")
    
    def on_cross_domain_event(self, event_type: str, handler: Callable):
        """
        Регистрация обработчика на кросс-доменные события.
        
        ARGS:
        - event_type: тип события для обработки
        - handler: обработчик события
        """
        if event_type not in self._cross_domain_listeners:
            self._cross_domain_listeners[event_type] = []
        self._cross_domain_listeners[event_type].append(handler)
    
    def enable_domain(self, domain: Union[EventDomain, str]):
        """Включение домена."""
        bus = self.get_bus(domain)
        bus.enable()
    
    def disable_domain(self, domain: Union[EventDomain, str]):
        """Выключение домена."""
        bus = self.get_bus(domain)
        bus.disable()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Получение статистики по всем доменам."""
        return {
            "domains": {
                domain.value: bus.get_stats()
                for domain, bus in self._buses.items()
            },
            "global_subscribers_count": len(self._global_subscribers),
            "cross_domain_listeners_count": len(self._cross_domain_listeners)
        }
    
    async def shutdown(self):
        """Корректное завершение работы всех шин."""
        self._self.event_bus_logger.info("Завершение работы EventBusManager")
        for domain, bus in self._buses.items():
            bus.disable()
            self._self.event_bus_logger.debug(f"Домен {domain.value} отключен")


# Глобальный менеджер шин событий (singleton)
_global_event_bus_manager: Optional[EventBusManager] = None


def get_event_bus_manager() -> EventBusManager:
    """
    Получение глобального менеджера шин событий.
    
    RETURNS:
    - EventBusManager: глобальный экземпляр
    """
    global _global_event_bus_manager
    if _global_event_bus_manager is None:
        _global_event_bus_manager = EventBusManager()
    return _global_event_bus_manager


def get_event_bus() -> EventBus:
    """
    Получение глобальной шины событий (для обратной совместимости).
    
    ВНИМАНИЕ: Используется только для обратной совместимости.
    Новый код должен использовать get_event_bus_manager().get_bus(domain).
    
    RETURNS:
    - EventBus: шина событий домена COMMON
    """
    manager = get_event_bus_manager()
    return manager.get_bus(EventDomain.COMMON)._event_bus


def reset_event_bus_manager():
    """Сброс глобального менеджера (для тестов)."""
    global _global_event_bus_manager
    _global_event_bus_manager = None
