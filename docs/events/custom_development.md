# Разработка системы событий под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению системы событий Koru AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующую систему событий и создавать новые компоненты для расширения функциональности системы.

## Архитектура системы событий

### 1. Интерфейсы и абстракции

Система событий построена на принципах открытости/закрытости и подстановки Лисков:

```python
# domain/abstractions/event_system.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable, Awaitable, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio

class EventType(Enum):
    """Типы событий системы"""
    # События агента
    AGENT_STATE_CHANGED = "agent_state_changed"
    AGENT_TASK_STARTED = "agent_task_started"
    AGENT_TASK_COMPLETED = "agent_task_completed"
    AGENT_TASK_FAILED = "agent_task_failed"
    AGENT_ERROR_OCCURRED = "agent_error_occurred"
    
    # События действий
    ATOMIC_ACTION_STARTED = "atomic_action_started"
    ATOMIC_ACTION_COMPLETED = "atomic_action_completed"
    ATOMIC_ACTION_FAILED = "atomic_action_failed"
    
    # События паттернов
    COMPOSABLE_PATTERN_STARTED = "composable_pattern_started"
    COMPOSABLE_PATTERN_COMPLETED = "composable_pattern_completed"
    COMPOSABLE_PATTERN_FAILED = "composable_pattern_failed"
    
    # Системные события
    SYSTEM_INITIALIZED = "system_initialized"
    SYSTEM_SHUTDOWN = "system_shutdown"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SECURITY_VIOLATION_DETECTED = "security_violation_detected"

@dataclass
class Event:
    """Модель события"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None
    source: str = None
    correlation_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class IEventPublisher(ABC):
    """Интерфейс издателя событий"""
    
    @abstractmethod
    async def publish(self, event_type: EventType, data: Dict[str, Any], **kwargs):
        """Опубликовать событие"""
        pass
    
    @abstractmethod
    async def bulk_publish(self, events: List[Event]):
        """Опубликовать несколько событий"""
        pass

class IEventSubscriber(ABC):
    """Интерфейс подписчика событий"""
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """Подписаться на событие"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """Отписаться от события"""
        pass

class IEventBus(IEventPublisher, IEventSubscriber, ABC):
    """Интерфейс шины событий"""
    
    @abstractmethod
    async def start(self):
        """Запустить шину событий"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Остановить шину событий"""
        pass
    
    @abstractmethod
    async def get_event_stats(self) -> Dict[str, Any]:
        """Получить статистику событий"""
        pass

class BaseEventBus(IEventBus, ABC):
    """Базовый класс для шины событий"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._subscribers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        self._is_running = False
        self._stats = {
            "published_events": 0,
            "handled_events": 0,
            "failed_events": 0,
            "start_time": None
        }
    
    async def start(self):
        """Запустить шину событий"""
        self._is_running = True
        self._stats["start_time"] = datetime.now()
    
    async def stop(self):
        """Остановить шину событий"""
        self._is_running = False
```

### 2. Реализация базовой шины событий

Базовая реализация шины событий:

```python
# infrastructure/gateways/event_bus.py
import asyncio
import logging
from typing import Dict, List, Callable, Awaitable
from domain.abstractions.event_system import BaseEventBus, Event, EventType
from collections import defaultdict, deque
import time

class EventBus(BaseEventBus):
    """Базовая реализация шины событий"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._queue = asyncio.Queue()
        self._worker_tasks = []
        self._max_workers = self.config.get("max_workers", 10)
        self._max_queue_size = self.config.get("max_queue_size", 1000)
        self._logger = logging.getLogger(__name__)
        self._event_log = deque(maxlen=self.config.get("log_retention", 1000))
        self._handlers = defaultdict(list)
        self._middleware = []
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """Подписаться на событие"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """Отписаться от события"""
        if event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], **kwargs) -> None:
        """Опубликовать событие"""
        if not self._is_running:
            raise RuntimeError("Шина событий не запущена")
        
        event = Event(
            type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=kwargs.get("source"),
            correlation_id=kwargs.get("correlation_id")
        )
        
        # Применить middleware к событию
        processed_event = await self._apply_middleware(event)
        
        # Добавить в очередь
        try:
            self._queue.put_nowait(processed_event)
            self._stats["published_events"] += 1
            
            # Логировать событие
            self._event_log.append({
                "timestamp": event.timestamp,
                "type": event.type.value,
                "source": event.source,
                "size": len(str(event.data))
            })
        except asyncio.QueueFull:
            self._logger.warning(f"Очередь событий переполнена, событие {event_type} потеряно")
    
    async def bulk_publish(self, events: List[Event]) -> None:
        """Опубликовать несколько событий"""
        for event in events:
            await self.publish(event.type, event.data, source=event.source, correlation_id=event.correlation_id)
    
    async def _apply_middleware(self, event: Event) -> Event:
        """Применить middleware к событию"""
        processed_event = event
        for middleware_func in self._middleware:
            processed_event = await middleware_func(processed_event)
        return processed_event
    
    async def _process_event(self, event: Event) -> None:
        """Обработать событие"""
        try:
            handlers = self._handlers.get(event.type, [])
            
            # Выполнить все обработчики асинхронно
            tasks = []
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        task = handler(event)
                    else:
                        task = asyncio.create_task(asyncio.to_thread(handler, event))
                    tasks.append(task)
                except Exception as e:
                    self._logger.error(f"Ошибка при создании задачи обработки события: {e}")
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self._stats["handled_events"] += 1
        except Exception as e:
            self._stats["failed_events"] += 1
            self._logger.error(f"Ошибка при обработке события {event.type}: {e}")
    
    async def _event_worker(self) -> None:
        """Рабочий процесс обработки событий"""
        while self._is_running:
            try:
                event = await self._queue.get()
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Ошибка в рабочем процессе событий: {e}")
    
    async def start(self) -> None:
        """Запустить шину событий"""
        await super().start()
        
        # Запустить рабочие процессы
        for _ in range(self._max_workers):
            worker_task = asyncio.create_task(self._event_worker())
            self._worker_tasks.append(worker_task)
    
    async def stop(self) -> None:
        """Остановить шину событий"""
        self._is_running = False
        
        # Отменить рабочие задачи
        for task in self._worker_tasks:
            task.cancel()
        
        # Дождаться завершения задач
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._worker_tasks.clear()
    
    async def get_event_stats(self) -> Dict[str, Any]:
        """Получить статистику событий"""
        uptime = (datetime.now() - self._stats["start_time"]).total_seconds() if self._stats["start_time"] else 0
        
        return {
            **self._stats,
            "uptime_seconds": uptime,
            "events_per_second": self._stats["published_events"] / uptime if uptime > 0 else 0,
            "queue_size": self._queue.qsize(),
            "active_handlers": {et.value: len(handlers) for et, handlers in self._handlers.items()}
        }
    
    def add_middleware(self, middleware_func: Callable[[Event], Awaitable[Event]]):
        """Добавить middleware для обработки событий"""
        self._middleware.append(middleware_func)
    
    def get_event_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить лог событий"""
        return list(self._event_log)[-limit:]
    
    def clear_event_log(self):
        """Очистить лог событий"""
        self._event_log.clear()
```

## Создание специфических компонентов системы событий

### 1. Специфические типы событий

Для расширения функциональности создайте специфические типы событий:

```python
# domain/models/specialized_events.py
from enum import Enum
from typing import Dict, Any
from domain.models.event import Event, EventType

class SpecializedEventType(Enum):
    """Специфические типы событий"""
    # События безопасности
    SECURITY_SCAN_STARTED = "security_scan_started"
    SECURITY_SCAN_COMPLETED = "security_scan_completed"
    SECURITY_VULNERABILITY_FOUND = "security_vulnerability_found"
    SECURITY_SCAN_FAILED = "security_scan_failed"
    
    # События анализа кода
    CODE_ANALYSIS_STARTED = "code_analysis_started"
    CODE_ANALYSIS_COMPLETED = "code_analysis_completed"
    CODE_QUALITY_ISSUE_FOUND = "code_quality_issue_found"
    CODE_COMPLEXITY_THRESHOLD_EXCEEDED = "code_complexity_threshold_exceeded"
    
    # События обработки данных
    DATA_PROCESSING_STARTED = "data_processing_started"
    DATA_VALIDATION_COMPLETED = "data_validation_completed"
    DATA_TRANSFORMATION_APPLIED = "data_transformation_applied"
    DATA_INTEGRITY_CHECK_FAILED = "data_integrity_check_failed"
    
    # События доменной адаптации
    DOMAIN_ADAPTATION_STARTED = "domain_adaptation_started"
    DOMAIN_ADAPTATION_COMPLETED = "domain_adaptation_completed"
    CAPABILITY_REGISTERED = "capability_registered"
    PATTERN_LOADED = "pattern_loaded"

class SpecializedEvent(Event):
    """Специфическое событие с дополнительными полями"""
    
    def __init__(
        self, 
        event_type: SpecializedEventType, 
        data: Dict[str, Any], 
        domain: str = None,
        priority: str = "normal",
        **kwargs
    ):
        super().__init__(event_type, data, **kwargs)
        self.domain = domain
        self.priority = priority
        self.processing_requirements = kwargs.get("processing_requirements", {})
        self.related_entities = kwargs.get("related_entities", [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать событие в словарь"""
        base_dict = super().to_dict()
        base_dict.update({
            "domain": self.domain,
            "priority": self.priority,
            "processing_requirements": self.processing_requirements,
            "related_entities": self.related_entities
        })
        return base_dict

# application/services/specialized_event_publisher.py
from domain.abstractions.event_system import IEventPublisher
from domain.models.specialized_event import SpecializedEvent, SpecializedEventType

class SpecializedEventPublisher(IEventPublisher):
    """Специфический публикатор событий для специфических задач"""
    
    def __init__(self, base_publisher: IEventPublisher, config: Dict[str, Any] = None):
        self._base_publisher = base_publisher
        self.config = config or {}
        self._domain_context = None
        self._security_filters = self.config.get("security_filters", [])
        self._priority_handlers = self.config.get("priority_handlers", {})
        self._rate_limiters = {}
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], **kwargs):
        """Опубликовать специфическое событие с дополнительной обработкой"""
        
        # Определить, является ли тип события специфическим
        if isinstance(event_type, SpecializedEventType):
            # Создать специфическое событие
            specialized_event = SpecializedEvent(
                event_type=event_type,
                data=data,
                domain=kwargs.get("domain"),
                priority=kwargs.get("priority", "normal"),
                processing_requirements=kwargs.get("processing_requirements", {}),
                related_entities=kwargs.get("related_entities", [])
            )
            
            # Применить фильтры безопасности
            if not self._apply_security_filters(specialized_event):
                return  # Событие отфильтровано
            
            # Применить ограничения скорости
            if not await self._check_rate_limit(event_type):
                return  # Превышен лимит скорости
            
            # Определить приоритет обработки
            priority = self._determine_event_priority(specialized_event)
            if priority in self._priority_handlers:
                # Обработать с помощью специфического обработчика приоритета
                await self._priority_handlers[priority](specialized_event)
            else:
                # Использовать базовый публикатор
                await self._base_publisher.publish(event_type, data, **kwargs)
        else:
            # Использовать базовый публикатор для обычных событий
            await self._base_publisher.publish(event_type, data, **kwargs)
    
    def _apply_security_filters(self, event: SpecializedEvent) -> bool:
        """Применить фильтры безопасности к событию"""
        for filter_func in self._security_filters:
            if not filter_func(event):
                return False  # Событие отфильтровано
        return True
    
    async def _check_rate_limit(self, event_type: EventType) -> bool:
        """Проверить ограничение скорости для типа события"""
        if event_type not in self._rate_limiters:
            # Создать рейт-лимитер для типа события
            from utils.rate_limiter import RateLimiter
            limits = self.config.get("rate_limits", {}).get(event_type.value, {"requests": 100, "window": 60})
            self._rate_limiters[event_type] = RateLimiter(limits["requests"], limits["window"])
        
        return await self._rate_limiters[event_type].is_allowed()
    
    def _determine_event_priority(self, event: SpecializedEvent) -> str:
        """Определить приоритет события"""
        # Определить приоритет на основе типа события и данных
        if event.type in [
            SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
            SpecializedEventType.DATA_INTEGRITY_CHECK_FAILED,
            SpecializedEventType.RESOURCE_LIMIT_EXCEEDED
        ]:
            return "critical"
        elif event.type in [
            SpecializedEventType.CODE_QUALITY_ISSUE_FOUND,
            SpecializedEventType.CODE_COMPLEXITY_THRESHOLD_EXCEEDED
        ]:
            return "high"
        else:
            return "normal"
    
    def set_domain_context(self, domain: str):
        """Установить контекст домена"""
        self._domain_context = domain
    
    def add_security_filter(self, filter_func: Callable[[SpecializedEvent], bool]):
        """Добавить фильтр безопасности"""
        self._security_filters.append(filter_func)
    
    def add_priority_handler(self, priority: str, handler: Callable[[SpecializedEvent], Awaitable[None]]):
        """Добавить обработчик приоритета"""
        self._priority_handlers[priority] = handler
    
    async def bulk_publish_specialized(self, events: List[SpecializedEvent]) -> None:
        """Опубликовать несколько специфических событий"""
        # Группировать события по приоритету
        priority_groups = {}
        for event in events:
            priority = self._determine_event_priority(event)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(event)
        
        # Обработать группы по приоритету
        for priority, group_events in priority_groups.items():
            if priority in self._priority_handlers:
                await self._priority_handlers[priority](group_events)
            else:
                # Опубликовать группу через базовый публикатор
                for event in group_events:
                    await self._base_publisher.publish(event.type, event.data, **event.kwargs)
```

### 2. Специфические обработчики событий

Создайте специфические обработчики для ваших задач:

```python
# application/handlers/specialized_handlers.py
from typing import Dict, Any, List
from domain.models.event import Event
from domain.models.specialized_event import SpecializedEvent, SpecializedEventType
from application.services.security_analyzer import SecurityAnalyzer
from application.services.code_analyzer import CodeAnalyzer
from application.services.data_processor import DataProcessor

class SecurityEventHandler:
    """Обработчик событий безопасности"""
    
    def __init__(self, security_analyzer: SecurityAnalyzer, notification_service: INotificationService):
        self.security_analyzer = security_analyzer
        self.notification_service = notification_service
    
    async def handle_security_scan_started(self, event: SpecializedEvent) -> None:
        """Обработать начало сканирования безопасности"""
        scan_id = event.data.get("scan_id")
        target = event.data.get("target")
        
        self.security_analyzer.register_scan(scan_id, target)
        
        # Отправить уведомление
        await self.notification_service.send_notification({
            "type": "info",
            "message": f"Начато сканирование безопасности для {target}",
            "scan_id": scan_id
        })
    
    async def handle_security_vulnerability_found(self, event: SpecializedEvent) -> None:
        """Обработать обнаружение уязвимости"""
        vulnerability = event.data.get("vulnerability")
        severity = vulnerability.get("severity", "medium")
        
        # Зарегистрировать уязвимость
        self.security_analyzer.register_vulnerability(vulnerability)
        
        # Отправить уведомление в зависимости от серьезности
        notification_type = "alert" if severity.lower() in ["high", "critical"] else "warning"
        
        await self.notification_service.send_notification({
            "type": notification_type,
            "message": f"Обнаружена уязвимость: {vulnerability.get('type', 'Unknown')}",
            "vulnerability": vulnerability,
            "severity": severity
        })
    
    async def handle_security_scan_completed(self, event: SpecializedEvent) -> None:
        """Обработать завершение сканирования безопасности"""
        scan_id = event.data.get("scan_id")
        results = event.data.get("results", {})
        
        # Обновить статистику сканирования
        self.security_analyzer.update_scan_results(scan_id, results)
        
        # Отправить итоговое уведомление
        await self.notification_service.send_notification({
            "type": "info",
            "message": f"Сканирование безопасности завершено",
            "scan_id": scan_id,
            "summary": self._generate_security_summary(results)
        })
    
    def _generate_security_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Сгенерировать сводку по результатам безопасности"""
        total_findings = sum(len(category) for category in results.values())
        high_severity = sum(
            len([f for f in category if f.get("severity", "").upper() in ["HIGH", "CRITICAL"]])
            for category in results.values()
        )
        
        return {
            "total_findings": total_findings,
            "high_severity_findings": high_severity,
            "low_severity_findings": total_findings - high_severity,
            "scan_duration": results.get("duration", 0)
        }

class CodeAnalysisEventHandler:
    """Обработчик событий анализа кода"""
    
    def __init__(self, code_analyzer: CodeAnalyzer, report_generator: IReportGenerator):
        self.code_analyzer = code_analyzer
        self.report_generator = report_generator
    
    async def handle_code_analysis_started(self, event: SpecializedEvent) -> None:
        """Обработать начало анализа кода"""
        analysis_id = event.data.get("analysis_id")
        target_file = event.data.get("target_file")
        
        self.code_analyzer.register_analysis(analysis_id, target_file)
    
    async def handle_code_quality_issue_found(self, event: SpecializedEvent) -> None:
        """Обработать обнаружение проблемы качества кода"""
        issue = event.data.get("issue")
        file_path = event.data.get("file_path")
        
        # Зарегистрировать проблему качества
        self.code_analyzer.register_quality_issue(file_path, issue)
    
    async def handle_code_analysis_completed(self, event: SpecializedEvent) -> None:
        """Обработать завершение анализа кода"""
        analysis_id = event.data.get("analysis_id")
        results = event.data.get("results", {})
        
        # Обновить результаты анализа
        self.code_analyzer.update_analysis_results(analysis_id, results)
        
        # Сгенерировать отчет
        report = await self.report_generator.generate_code_analysis_report(results)
        
        # Сохранить отчет
        await self._save_analysis_report(analysis_id, report)
    
    async def _save_analysis_report(self, analysis_id: str, report: Dict[str, Any]) -> None:
        """Сохранить отчет анализа"""
        # Реализация сохранения отчета
        pass

class DataProcessingEventHandler:
    """Обработчик событий обработки данных"""
    
    def __init__(self, data_processor: DataProcessor, monitoring_service: IMonitoringService):
        self.data_processor = data_processor
        self.monitoring_service = monitoring_service
    
    async def handle_data_processing_started(self, event: SpecializedEvent) -> None:
        """Обработать начало обработки данных"""
        process_id = event.data.get("process_id")
        data_source = event.data.get("data_source")
        
        # Регистрация процесса обработки
        self.data_processor.register_process(process_id, data_source)
        
        # Мониторинг начала процесса
        await self.monitoring_service.record_process_start(process_id, data_source)
    
    async def handle_data_transformation_applied(self, event: SpecializedEvent) -> None:
        """Обработать применение трансформации данных"""
        process_id = event.data.get("process_id")
        transformation_type = event.data.get("transformation_type")
        records_processed = event.data.get("records_processed", 0)
        
        # Обновить статистику трансформации
        self.data_processor.update_transformation_stats(
            process_id, 
            transformation_type, 
            records_processed
        )
        
        # Мониторинг трансформации
        await self.monitoring_service.record_transformation(
            process_id, 
            transformation_type, 
            records_processed
        )
    
    async def handle_data_integrity_check_failed(self, event: SpecializedEvent) -> None:
        """Обработать ошибку проверки целостности данных"""
        process_id = event.data.get("process_id")
        error_details = event.data.get("error_details")
        
        # Зарегистрировать ошибку целостности
        self.data_processor.register_integrity_error(process_id, error_details)
        
        # Мониторинг ошибки
        await self.monitoring_service.record_integrity_error(process_id, error_details)
        
        # Отправить оповещение о критической ошибке
        await self._notify_critical_error("data_integrity", process_id, error_details)
    
    async def _notify_critical_error(self, error_type: str, process_id: str, details: Dict[str, Any]) -> None:
        """Уведомить о критической ошибке"""
        # Реализация уведомления о критической ошибке
        pass

class DomainAdaptationEventHandler:
    """Обработчик событий адаптации к домену"""
    
    def __init__(self, domain_manager: DomainManager, capability_registry: CapabilityRegistry):
        self.domain_manager = domain_manager
        self.capability_registry = capability_registry
    
    async def handle_domain_adaptation_started(self, event: SpecializedEvent) -> None:
        """Обработать начало адаптации к домену"""
        domain_type = event.data.get("domain_type")
        agent_id = event.data.get("agent_id")
        
        # Регистрация процесса адаптации
        self.domain_manager.register_adaptation_process(agent_id, domain_type)
    
    async def handle_capability_registered(self, event: SpecializedEvent) -> None:
        """Обработать регистрацию возможности"""
        capability_name = event.data.get("capability_name")
        domain_type = event.data.get("domain_type")
        
        # Регистрация возможности в реестре
        self.capability_registry.register_capability(capability_name, domain_type)
    
    async def handle_pattern_loaded(self, event: SpecializedEvent) -> None:
        """Обработать загрузку паттерна"""
        pattern_name = event.data.get("pattern_name")
        domain_type = event.data.get("domain_type")
        
        # Обновить информацию о загруженных паттернах
        self.domain_manager.register_loaded_pattern(domain_type, pattern_name)
```

## Интеграция специфических компонентов

### 1. Фабрика специфических компонентов

Для создания и управления специфическими компонентами системы событий:

```python
# application/factories/specialized_event_factory.py
from typing import Dict, Any, Type
from domain.abstractions.event_system import IEventPublisher, IEventSubscriber
from application.handlers.specialized_handlers import (
    SecurityEventHandler, 
    CodeAnalysisEventHandler, 
    DataProcessingEventHandler,
    DomainAdaptationEventHandler
)
from application.services.security_analyzer import SecurityAnalyzer
from application.services.code_analyzer import CodeAnalyzer
from application.services.data_processor import DataProcessor
from application.services.domain_manager import DomainManager

class SpecializedEventFactory:
    """Фабрика для создания специфических компонентов системы событий"""
    
    def __init__(self, base_publisher: IEventPublisher, config: Dict[str, Any] = None):
        self.base_publisher = base_publisher
        self.config = config or {}
        self._handler_instances = {}
        self._analyzer_services = {}
    
    def create_specialized_publisher(self, publisher_type: str, **kwargs) -> IEventPublisher:
        """Создать специфический публикатор событий"""
        if publisher_type == "security":
            from application.services.security_event_publisher import SecurityEventPublisher
            return SecurityEventPublisher(self.base_publisher, {**self.config, **kwargs})
        elif publisher_type == "analysis":
            from application.services.analysis_event_publisher import AnalysisEventPublisher
            return AnalysisEventPublisher(self.base_publisher, {**self.config, **kwargs})
        elif publisher_type == "data_processing":
            from application.services.data_event_publisher import DataEventPublisher
            return DataEventPublisher(self.base_publisher, {**self.config, **kwargs})
        else:
            raise ValueError(f"Неизвестный тип специфического публикатора: {publisher_type}")
    
    def create_specialized_handler(self, handler_type: str, **dependencies) -> Any:
        """Создать специфический обработчик событий"""
        if handler_type == "security":
            return SecurityEventHandler(
                security_analyzer=dependencies.get("security_analyzer"),
                notification_service=dependencies.get("notification_service")
            )
        elif handler_type == "code_analysis":
            return CodeAnalysisEventHandler(
                code_analyzer=dependencies.get("code_analyzer"),
                report_generator=dependencies.get("report_generator")
            )
        elif handler_type == "data_processing":
            return DataProcessingEventHandler(
                data_processor=dependencies.get("data_processor"),
                monitoring_service=dependencies.get("monitoring_service")
            )
        elif handler_type == "domain_adaptation":
            return DomainAdaptationEventHandler(
                domain_manager=dependencies.get("domain_manager"),
                capability_registry=dependencies.get("capability_registry")
            )
        else:
            raise ValueError(f"Неизвестный тип специфического обработчика: {handler_type}")
    
    def register_handlers_to_event_bus(self, event_bus: IEventSubscriber, handler_type: str, **dependencies):
        """Зарегистрировать специфические обработчики в шине событий"""
        handler = self.create_specialized_handler(handler_type, **dependencies)
        
        # Определить тип обработчика и зарегистрировать соответствующие события
        if isinstance(handler, SecurityEventHandler):
            event_bus.subscribe(SpecializedEventType.SECURITY_SCAN_STARTED, handler.handle_security_scan_started)
            event_bus.subscribe(SpecializedEventType.SECURITY_VULNERABILITY_FOUND, handler.handle_security_vulnerability_found)
            event_bus.subscribe(SpecializedEventType.SECURITY_SCAN_COMPLETED, handler.handle_security_scan_completed)
        elif isinstance(handler, CodeAnalysisEventHandler):
            event_bus.subscribe(SpecializedEventType.CODE_ANALYSIS_STARTED, handler.handle_code_analysis_started)
            event_bus.subscribe(SpecializedEventType.CODE_QUALITY_ISSUE_FOUND, handler.handle_code_quality_issue_found)
            event_bus.subscribe(SpecializedEventType.CODE_ANALYSIS_COMPLETED, handler.handle_code_analysis_completed)
        elif isinstance(handler, DataProcessingEventHandler):
            event_bus.subscribe(SpecializedEventType.DATA_PROCESSING_STARTED, handler.handle_data_processing_started)
            event_bus.subscribe(SpecializedEventType.DATA_TRANSFORMATION_APPLIED, handler.handle_data_transformation_applied)
            event_bus.subscribe(SpecializedEventType.DATA_INTEGRITY_CHECK_FAILED, handler.handle_data_integrity_check_failed)
        elif isinstance(handler, DomainAdaptationEventHandler):
            event_bus.subscribe(SpecializedEventType.DOMAIN_ADAPTATION_STARTED, handler.handle_domain_adaptation_started)
            event_bus.subscribe(SpecializedEventType.CAPABILITY_REGISTERED, handler.handle_capability_registered)
            event_bus.subscribe(SpecializedEventType.PATTERN_LOADED, handler.handle_pattern_loaded)
        
        return handler
    
    def create_analyzer_service(self, analyzer_type: str, **kwargs) -> Any:
        """Создать сервис анализа"""
        if analyzer_type == "security":
            return SecurityAnalyzer(**kwargs)
        elif analyzer_type == "code":
            return CodeAnalyzer(**kwargs)
        elif analyzer_type == "data":
            return DataProcessor(**kwargs)
        else:
            raise ValueError(f"Неизвестный тип анализатора: {analyzer_type}")
    
    def get_or_create_analyzer(self, analyzer_type: str, **kwargs) -> Any:
        """Получить или создать экземпляр анализатора"""
        key = f"{analyzer_type}_{hash(str(kwargs))}"
        
        if key not in self._analyzer_services:
            self._analyzer_services[key] = self.create_analyzer_service(analyzer_type, **kwargs)
        
        return self._analyzer_services[key]

class AdvancedEventFactory(SpecializedEventFactory):
    """Расширенная фабрика событий с поддержкой сложных конфигураций"""
    
    def __init__(self, base_publisher: IEventPublisher, config: Dict[str, Any] = None):
        super().__init__(base_publisher, config)
        self._middleware_registry = {}
        self._filter_registry = {}
        self._aggregator_registry = {}
    
    def create_configurable_event_publisher(
        self, 
        publisher_type: str, 
        middleware: List[Callable] = None,
        filters: List[Callable] = None,
        aggregators: List[Callable] = None,
        **kwargs
    ) -> IEventPublisher:
        """Создать настраиваемый публикатор событий"""
        
        # Создать базовый специфический публикатор
        publisher = self.create_specialized_publisher(publisher_type, **kwargs)
        
        # Добавить middleware
        if middleware:
            for mw_func in middleware:
                if hasattr(publisher, 'add_middleware'):
                    publisher.add_middleware(mw_func)
        
        # Добавить фильтры
        if filters:
            for filter_func in filters:
                if hasattr(publisher, 'add_filter'):
                    publisher.add_filter(filter_func)
        
        # Добавить агрегаторы
        if aggregators:
            for agg_func in aggregators:
                if hasattr(publisher, 'add_aggregator'):
                    publisher.add_aggregator(agg_func)
        
        return publisher
    
    def register_middleware(self, name: str, middleware_func: Callable):
        """Зарегистрировать middleware"""
        self._middleware_registry[name] = middleware_func
    
    def register_filter(self, name: str, filter_func: Callable):
        """Зарегистрировать фильтр"""
        self._filter_registry[name] = filter_func
    
    def register_aggregator(self, name: str, aggregator_func: Callable):
        """Зарегистрировать агрегатор"""
        self._aggregator_registry[name] = aggregator_func
    
    def get_registered_component(self, component_type: str, name: str):
        """Получить зарегистрированный компонент"""
        registries = {
            "middleware": self._middleware_registry,
            "filter": self._filter_registry,
            "aggregator": self._aggregator_registry
        }
        
        if component_type in registries:
            return registries[component_type].get(name)
        return None
```

### 2. Использование специфических компонентов

Пример использования специфических компонентов системы событий:

```python
# specialized_events_usage.py
from application.factories.advanced_event_factory import AdvancedEventFactory
from domain.models.specialized_event import SpecializedEventType
from application.services.notification_service import NotificationService
from application.services.report_generator import ReportGenerator
from application.services.monitoring_service import MonitoringService

async def specialized_events_example():
    """Пример использования специфических компонентов системы событий"""
    
    # Создать базовую шину событий
    base_event_bus = EventBus({
        "max_workers": 20,
        "max_queue_size": 2000
    })
    await base_event_bus.start()
    
    # Создать расширенную фабрику событий
    event_factory = AdvancedEventFactory(
        base_publisher=base_event_bus,
        config={
            "security_filters_enabled": True,
            "rate_limiting_enabled": True,
            "priority_handling_enabled": True
        }
    )
    
    # Создать сервисы
    notification_service = NotificationService()
    report_generator = ReportGenerator()
    monitoring_service = MonitoringService()
    
    # Создать специфические анализаторы
    security_analyzer = event_factory.get_or_create_analyzer(
        "security",
        threshold_levels={"high": 5, "critical": 1}
    )
    
    code_analyzer = event_factory.get_or_create_analyzer(
        "code",
        quality_threshold=85
    )
    
    data_processor = event_factory.get_or_create_analyzer(
        "data",
        integrity_check_enabled=True
    )
    
    # Зарегистрировать специфические обработчики
    security_handler = event_factory.register_handlers_to_event_bus(
        base_event_bus,
        "security",
        security_analyzer=security_analyzer,
        notification_service=notification_service
    )
    
    code_analysis_handler = event_factory.register_handlers_to_event_bus(
        base_event_bus,
        "code_analysis", 
        code_analyzer=code_analyzer,
        report_generator=report_generator
    )
    
    data_processing_handler = event_factory.register_handlers_to_event_bus(
        base_event_bus,
        "data_processing",
        data_processor=data_processor,
        monitoring_service=monitoring_service
    )
    
    # Создать специфический публикатор с настройками
    security_publisher = event_factory.create_configurable_event_publisher(
        "security",
        middleware=[add_correlation_id_middleware, security_enrichment_middleware],
        filters=[sensitive_data_filter, rate_limit_filter],
        aggregators=[security_event_aggregator],
        domain="security_analysis"
    )
    
    # Опубликовать специфические события
    await security_publisher.publish(
        SpecializedEventType.SECURITY_SCAN_STARTED,
        {
            "scan_id": "scan_12345",
            "target": "./src/main.py",
            "scan_type": "vulnerability"
        },
        domain="security",
        priority="high"
    )
    
    # Опубликовать событие обнаружения уязвимости
    await security_publisher.publish(
        SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
        {
            "vulnerability": {
                "type": "SQL_INJECTION",
                "severity": "CRITICAL",
                "location": {"file": "./src/main.py", "line": 45},
                "description": "Potential SQL injection in user input handling"
            },
            "scan_id": "scan_12345"
        },
        domain="security",
        priority="critical"
    )
    
    # Опубликовать событие завершения сканирования
    await security_publisher.publish(
        SpecializedEventType.SECURITY_SCAN_COMPLETED,
        {
            "scan_id": "scan_12345",
            "results": {
                "vulnerabilities_found": 1,
                "scan_duration": 45.2,
                "files_scanned": 25
            }
        },
        domain="security",
        priority="normal"
    )
    
    # Дождаться обработки всех событий
    await base_event_bus.stop()
    
    print("Специфические события обработаны успешно")
    
    return {
        "security_events_published": 3,
        "handlers_registered": 3
    }

# Интеграция с агентами
async def agent_events_integration_example():
    """Пример интеграции специфических событий с агентами"""
    
    # Создать базовую шину событий
    event_bus = EventBus()
    await event_bus.start()
    
    # Создать фабрику событий
    event_factory = SpecializedEventFactory(event_bus)
    
    # Создать специфические сервисы
    security_analyzer = event_factory.get_or_create_analyzer("security")
    notification_service = NotificationService()
    
    # Создать обработчик безопасности
    security_handler = event_factory.create_specialized_handler(
        "security",
        security_analyzer=security_analyzer,
        notification_service=notification_service
    )
    
    # Зарегистрировать обработчик в шине событий
    event_bus.subscribe(SpecializedEventType.SECURITY_VULNERABILITY_FOUND, security_handler.handle_security_vulnerability_found)
    
    # Создать агента с публикатором событий
    from application.factories.agent_factory import AgentFactory
    agent_factory = AgentFactory()
    
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Установить публикатор событий для агента
    agent.set_event_publisher(event_bus)
    
    # Выполнить задачу, которая может генерировать специфические события
    task_result = await agent.execute_task(
        task_description="Проанализируй этот Python код на наличие уязвимостей безопасности",
        context={
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python"
        }
    )
    
    # Получить статистику по событиям
    event_stats = await event_bus.get_event_stats()
    print(f"Статистика событий: {event_stats}")
    
    # Получить последние события
    recent_events = event_bus.get_event_log(limit=10)
    print(f"Последние события: {recent_events}")
    
    await event_bus.stop()
    
    return task_result, event_stats

# Middleware примеры
async def add_correlation_id_middleware(event: Event) -> Event:
    """Middleware для добавления correlation ID"""
    if not event.correlation_id:
        import uuid
        event.correlation_id = str(uuid.uuid4())
    return event

async def security_enrichment_middleware(event: SpecializedEvent) -> SpecializedEvent:
    """Middleware для обогащения событий безопасности"""
    if isinstance(event, SpecializedEvent) and event.type in [
        SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
        SpecializedEventType.SECURITY_SCAN_STARTED
    ]:
        # Добавить дополнительную информацию безопасности
        event.data["security_context"] = {
            "timestamp": time.time(),
            "source_ip": get_current_ip(),  # В реальной реализации
            "user_agent": get_current_user_agent()  # В реальной реализации
        }
    return event

def sensitive_data_filter(event: SpecializedEvent) -> bool:
    """Фильтр для чувствительных данных"""
    if hasattr(event, 'data') and event.data:
        sensitive_keywords = ['password', 'token', 'api_key', 'secret']
        for keyword in sensitive_keywords:
            if keyword in str(event.data).lower():
                # Логировать инцидент безопасности
                log_security_incident(f"Sensitve data detected in event: {event.type}")
                return False  # Отфильтровать событие
    return True

def rate_limit_filter(event: SpecializedEvent) -> bool:
    """Фильтр по ограничению частоты"""
    # В реальной реализации здесь будет проверка частоты событий
    # с использованием рейт-лимитера
    return True  # Пока возвращаем True для примера

def security_event_aggregator(events: List[SpecializedEvent]) -> List[SpecializedEvent]:
    """Агрегатор событий безопасности"""
    if not events:
        return events
    
    # Агрегировать события безопасности по типу уязвимости
    aggregated_events = []
    vulnerability_groups = {}
    
    for event in events:
        if event.type == SpecializedEventType.SECURITY_VULNERABILITY_FOUND:
            vuln_type = event.data.get("vulnerability", {}).get("type", "unknown")
            if vuln_type not in vulnerability_groups:
                vulnerability_groups[vuln_type] = []
            vulnerability_groups[vuln_type].append(event)
        else:
            aggregated_events.append(event)
    
    # Создать агрегированные события для каждой группы уязвимостей
    for vuln_type, vuln_events in vulnerability_groups.items():
        aggregated_data = {
            "vulnerability_type": vuln_type,
            "count": len(vuln_events),
            "first_occurrence": min(e.timestamp for e in vuln_events),
            "last_occurrence": max(e.timestamp for e in vuln_events),
            "affected_files": list(set(
                e.data.get("vulnerability", {}).get("location", {}).get("file", "") 
                for e in vuln_events
            ))
        }
        
        aggregated_event = SpecializedEvent(
            event_type=SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
            data=aggregated_data,
            priority="aggregated"
        )
        aggregated_events.append(aggregated_event)
    
    return aggregated_events
```

## Лучшие практики

### 1. Безопасность и фильтрация

Обязательно реализуйте фильтрацию и безопасность:

```python
def create_security_filtered_event_bus(base_bus: IEventBus) -> IEventBus:
    """Создать шину событий с фильтрацией безопасности"""
    
    # Добавить middleware для фильтрации чувствительных данных
    def security_filter_middleware(event: Event) -> Event:
        if hasattr(event, 'data') and isinstance(event.data, dict):
            # Фильтровать чувствительные поля
            filtered_data = event.data.copy()
            sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
            
            for field in sensitive_fields:
                if field in filtered_data:
                    filtered_data[field] = "***FILTERED***"
            
            event.data = filtered_data
        
        return event
    
    # Добавить middleware к базовой шине
    if hasattr(base_bus, 'add_middleware'):
        base_bus.add_middleware(security_filter_middleware)
    
    return base_bus

def create_priority_based_event_handler(base_handler: Callable) -> Callable:
    """Создать обработчик событий на основе приоритета"""
    
    async def priority_handler(event: Event):
        # Определить приоритет события
        priority = getattr(event, 'priority', 'normal')
        
        if priority == 'critical':
            # Обработать критические события немедленно
            return await handle_critical_event(event)
        elif priority == 'high':
            # Обработать высокоприоритетные события с высоким приоритетом
            return await handle_high_priority_event(event)
        else:
            # Обработать обычные события стандартно
            return await base_handler(event)
    
    return priority_handler
```

### 2. Мониторинг и логирование

Обеспечьте мониторинг специфических событий:

```python
class MonitoredEventBus(EventBus):
    """Шина событий с мониторингом"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._monitoring_service = self._initialize_monitoring()
        self._event_counters = defaultdict(int)
        self._event_timers = defaultdict(list)
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], **kwargs) -> None:
        """Опубликовать событие с мониторингом"""
        
        start_time = time.time()
        
        # Опубликовать событие
        await super().publish(event_type, data, **kwargs)
        
        # Обновить метрики
        end_time = time.time()
        processing_time = end_time - start_time
        
        self._event_counters[event_type.value] += 1
        self._event_timers[event_type.value].append(processing_time)
        
        # Отправить метрики в систему мониторинга
        await self._monitoring_service.record_event_metrics({
            "event_type": event_type.value,
            "processing_time": processing_time,
            "timestamp": time.time()
        })
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Получить статистику мониторинга"""
        stats = {}
        
        for event_type, timers in self._event_timers.items():
            if timers:
                stats[event_type] = {
                    "count": self._event_counters[event_type],
                    "avg_processing_time": sum(timers) / len(timers),
                    "min_processing_time": min(timers),
                    "max_processing_time": max(timers),
                    "total_processing_time": sum(timers)
                }
        
        return stats
    
    def _initialize_monitoring(self):
        """Инициализировать сервис мониторинга"""
        # В реальной реализации здесь будет инициализация
        # сервиса мониторинга (Prometheus, StatsD и т.д.)
        pass
```

### 3. Тестирование специфических компонентов

Создавайте тесты для каждого специфического компонента:

```python
# test_specialized_events.py
import pytest
from unittest.mock import AsyncMock, Mock, call
from domain.models.specialized_event import SpecializedEvent, SpecializedEventType

class TestSpecializedEventPublisher:
    @pytest.mark.asyncio
    async def test_security_event_publishing(self):
        """Тест публикации событий безопасности"""
        # Создать мок базового публикатора
        mock_base_publisher = AsyncMock()
        
        # Создать специфический публикатор
        security_publisher = SpecializedEventPublisher(
            base_publisher=mock_base_publisher,
            config={
                "security_filters": [],
                "rate_limits": {"SECURITY_VULNERABILITY_FOUND": {"requests": 10, "window": 60}}
            }
        )
        
        # Опубликовать событие
        await security_publisher.publish(
            SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
            {
                "vulnerability": {
                    "type": "SQL_INJECTION",
                    "severity": "HIGH",
                    "location": {"file": "test.py", "line": 10}
                }
            },
            domain="security",
            priority="high"
        )
        
        # Проверить, что базовый публикатор был вызван
        mock_base_publisher.publish.assert_called_once()
        
        # Проверить аргументы вызова
        args, kwargs = mock_base_publisher.publish.call_args
        assert args[0] == SpecializedEventType.SECURITY_VULNERABILITY_FOUND
        assert "vulnerability" in args[1]

class TestSecurityEventHandler:
    @pytest.mark.asyncio
    async def test_vulnerability_found_handling(self):
        """Тест обработки события обнаружения уязвимости"""
        # Создать моки зависимостей
        mock_security_analyzer = Mock()
        mock_notification_service = AsyncMock()
        
        # Создать обработчик
        handler = SecurityEventHandler(mock_security_analyzer, mock_notification_service)
        
        # Создать событие
        event = SpecializedEvent(
            event_type=SpecializedEventType.SECURITY_VULNERABILITY_FOUND,
            data={
                "vulnerability": {
                    "type": "XSS",
                    "severity": "MEDIUM",
                    "description": "Cross-site scripting vulnerability"
                },
                "scan_id": "test_scan_123"
            }
        )
        
        # Обработать событие
        await handler.handle_security_vulnerability_found(event)
        
        # Проверить, что зависимости были вызваны корректно
        mock_security_analyzer.register_vulnerability.assert_called_once_with(
            event.data["vulnerability"]
        )
        
        # Проверить, что было отправлено уведомление
        mock_notification_service.send_notification.assert_called_once()
        notification_args = mock_notification_service.send_notification.call_args[0][0]
        assert notification_args["type"] == "warning"
        assert "XSS" in notification_args["message"]

class TestEventBusMonitoring:
    @pytest.mark.asyncio
    async def test_event_timing_monitoring(self):
        """Тест мониторинга времени обработки событий"""
        
        # Создать мониторинговую шину событий
        monitored_bus = MonitoredEventBus()
        await monitored_bus.start()
        
        # Опубликовать несколько событий
        for i in range(5):
            await monitored_bus.publish(EventType.AGENT_TASK_STARTED, {"task_id": f"task_{i}"})
        
        # Получить статистику
        stats = monitored_bus.get_monitoring_stats()
        
        # Проверить, что статистика содержит данные
        assert EventType.AGENT_TASK_STARTED.value in stats
        event_stats = stats[EventType.AGENT_TASK_STARTED.value]
        assert event_stats["count"] == 5
        assert "avg_processing_time" in event_stats
        assert "min_processing_time" in event_stats
        assert "max_processing_time" in event_stats
        
        await monitored_bus.stop()
```

Эти примеры показывают, как адаптировать и расширять систему событий Koru AI Agent Framework под специфические задачи, обеспечивая безопасность, производительность и надежность системы.