# Разработка ядра системы под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению ядра Composable AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующие компоненты ядра и создавать новые для расширения функциональности системы.

## Архитектура ядра системы

### 1. Среда выполнения агента (Agent Runtime)

Среда выполнения управляет жизненным циклом агента и координирует выполнение задач:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.models.agent.agent_state import AgentState
from domain.abstractions.event_system import IEventPublisher
from application.orchestration.atomic_actions import AtomicActionExecutor

class IAgentRuntime(ABC):
    """Интерфейс среды выполнения агента"""
    
    @property
    @abstractmethod
    def state(self) -> AgentState:
        """Состояние агента"""
        pass
    
    @abstractmethod
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с указанным описанием и контекстом"""
        pass
    
    @abstractmethod
    async def execute_atomic_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить атомарное действие"""
        pass
    
    @abstractmethod
    async def execute_composable_pattern(self, pattern_name: str, context: Any) -> Dict[str, Any]:
        """Выполнить компонуемый паттерн"""
        pass

class AgentRuntime(IAgentRuntime):
    """Среда выполнения агента"""
    
    def __init__(
        self,
        initial_state: AgentState,
        event_publisher: IEventPublisher,
        action_executor: AtomicActionExecutor
    ):
        self.state = initial_state
        self.event_publisher = event_publisher
        self.action_executor = action_executor
        self.pattern_executor = PatternExecutor()
        self._is_running = False
        self._execution_context = {}
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу"""
        if not self._is_running:
            await self._initialize_runtime()
        
        try:
            # Обновить состояние
            self.state.step += 1
            
            # Опубликовать событие начала задачи
            await self.event_publisher.publish("task_started", {
                "task_description": task_description,
                "step": self.state.step
            })
            
            # Выполнить основную логику задачи
            result = await self._execute_task_logic(task_description, context)
            
            # Обновить состояние при успехе
            self.state.register_progress(progressed=True)
            
            # Опубликовать событие завершения задачи
            await self.event_publisher.publish("task_completed", {
                "task_description": task_description,
                "result": result,
                "step": self.state.step
            })
            
            return {"success": True, **result}
        except Exception as e:
            self.state.register_error()
            self.state.register_progress(progressed=False)
            
            # Опубликовать событие ошибки
            await self.event_publisher.publish("task_failed", {
                "task_description": task_description,
                "error": str(e),
                "step": self.state.step
            })
            
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи: {str(e)}",
                "step": self.state.step
            }
    
    async def execute_atomic_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить атомарное действие"""
        try:
            result = await self.action_executor.execute_action(action_name, parameters)
            
            # Опубликовать событие выполнения действия
            await self.event_publisher.publish("action_executed", {
                "action_name": action_name,
                "parameters": parameters,
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "error": f"Ошибка при выполнении атомарного действия {action_name}: {str(e)}"
            }
            
            # Опубликовать событие ошибки действия
            await self.event_publisher.publish("action_failed", {
                "action_name": action_name,
                "parameters": parameters,
                "error": str(e)
            })
            
            return error_result
    
    async def execute_composable_pattern(self, pattern_name: str, context: Any) -> Dict[str, Any]:
        """Выполнить компонуемый паттерн"""
        try:
            result = await self.pattern_executor.execute_pattern(pattern_name, context)
            
            # Опубликовать событие выполнения паттерна
            await self.event_publisher.publish("pattern_executed", {
                "pattern_name": pattern_name,
                "context": context,
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "error": f"Ошибка при выполнении паттерна {pattern_name}: {str(e)}"
            }
            
            # Опубликовать событие ошибки паттерна
            await self.event_publisher.publish("pattern_failed", {
                "pattern_name": pattern_name,
                "context": context,
                "error": str(e)
            })
            
            return error_result
    
    async def _initialize_runtime(self):
        """Инициализировать среду выполнения"""
        self._is_running = True
        
        # Инициализировать компоненты
        await self.action_executor.initialize()
        await self.pattern_executor.initialize()
        
        # Опубликовать событие инициализации
        await self.event_publisher.publish("runtime_initialized", {
            "timestamp": time.time()
        })
    
    async def _execute_task_logic(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить основную логику задачи"""
        # Определить тип задачи
        task_type = self._determine_task_type(task_description)
        
        if task_type == "analysis":
            return await self._execute_analysis_task(task_description, context)
        elif task_type == "data_processing":
            return await self._execute_data_processing_task(task_description, context)
        elif task_type == "content_generation":
            return await self._execute_content_generation_task(task_description, context)
        else:
            return await self._execute_general_task(task_description, context)
    
    def _determine_task_type(self, task_description: str) -> str:
        """Определить тип задачи по описанию"""
        desc_lower = task_description.lower()
        
        if any(keyword in desc_lower for keyword in ["анализ", "анализировать", "security", "vulnerability"]):
            return "analysis"
        elif any(keyword in desc_lower for keyword in ["данны", "data", "sql", "query"]):
            return "data_processing"
        elif any(keyword in desc_lower for keyword in ["генер", "create", "write", "generate"]):
            return "content_generation"
        else:
            return "general"
    
    async def _execute_analysis_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу анализа"""
        # Реализация задачи анализа
        pass
    
    async def _execute_data_processing_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу обработки данных"""
        # Реализация задачи обработки данных
        pass
    
    async def _execute_content_generation_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу генерации контента"""
        # Реализация задачи генерации контента
        pass
    
    async def _execute_general_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить общую задачу"""
        # Реализация общей задачи
        pass
```

### 2. Система событий (Event System)

Система событий обеспечивает коммуникацию между компонентами:

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from enum import Enum
import asyncio
import time

class EventType(Enum):
    """Типы событий"""
    AGENT_STATE_CHANGED = "agent_state_changed"
    ACTION_EXECUTED = "action_executed"
    PATTERN_EXECUTED = "pattern_executed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ERROR_OCCURRED = "error_occurred"
    RUNTIME_INITIALIZED = "runtime_initialized"

class IEventPublisher(ABC):
    """Интерфейс издателя событий"""
    
    @abstractmethod
    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """Опубликовать событие"""
        pass

class IEventSubscriber(ABC):
    """Интерфейс подписчика событий"""
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable):
        """Подписаться на событие"""
        pass

class EventBus(IEventPublisher, IEventSubscriber):
    """Шина событий"""
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self._event_queue = asyncio.Queue()
        self._running = False
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Подписаться на событие"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """Опубликовать событие"""
        if event_type in self.subscribers:
            # Создать задачу для асинхронной обработки событий
            for handler in self.subscribers[event_type]:
                try:
                    # Выполнить обработчик асинхронно
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_type, data)
                    else:
                        handler(event_type, data)
                except Exception as e:
                    print(f"Ошибка при обработке события {event_type}: {e}")
    
    async def start_listening(self):
        """Начать прослушивание событий"""
        self._running = True
        
        while self._running:
            try:
                # Получить событие из очереди
                event = await self._event_queue.get()
                
                # Опубликовать событие
                await self.publish(event["type"], event["data"])
                
                # Отметить обработку события
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка при прослушивании событий: {e}")
    
    async def stop_listening(self):
        """Остановить прослушивание событий"""
        self._running = False
```

## Расширение ядра системы

### 1. Создание специфической среды выполнения

Для адаптации среды выполнения под специфические задачи:

```python
class CustomAgentRuntime(AgentRuntime):
    """Специфическая среда выполнения для конкретных задач"""
    
    def __init__(
        self,
        initial_state: AgentState,
        event_publisher: IEventPublisher,
        action_executor: AtomicActionExecutor,
        custom_config: Dict[str, Any] = None
    ):
        super().__init__(initial_state, event_publisher, action_executor)
        self.custom_config = custom_config or {}
        self._custom_components = {}
        self._task_priorities = {}
        
        # Инициализировать специфические компоненты
        self._initialize_custom_components()
    
    def _initialize_custom_components(self):
        """Инициализировать специфические компоненты"""
        # Инициализировать компоненты на основе конфигурации
        if "memory_manager" in self.custom_config:
            self._custom_components["memory_manager"] = MemoryManager(
                **self.custom_config["memory_manager"]
            )
        
        if "context_enhancer" in self.custom_config:
            self._custom_components["context_enhancer"] = ContextEnhancer(
                **self.custom_config["context_enhancer"]
            )
        
        if "task_scheduler" in self.custom_config:
            self._custom_components["task_scheduler"] = TaskScheduler(
                **self.custom_config["task_scheduler"]
            )
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Расширенное выполнение задачи с использованием специфических компонентов"""
        
        # Использовать планировщик задач, если доступен
        if "task_scheduler" in self._custom_components:
            scheduled_task = await self._custom_components["task_scheduler"].schedule_task(
                task_description, context
            )
            task_description = scheduled_task["description"]
            context = scheduled_task.get("context", context)
        
        # Улучшить контекст, если доступен улучшатель
        if "context_enhancer" in self._custom_components and context:
            enhanced_context = await self._custom_components["context_enhancer"].enhance_context(
                task_description, context
            )
            context = {**context, **enhanced_context}
        
        # Вызов базовой реализации
        result = await super().execute_task(task_description, context)
        
        # Обновить память агента, если доступен менеджер памяти
        if "memory_manager" in self._custom_components:
            await self._custom_components["memory_manager"].update_memory(result)
        
        return result
    
    async def _execute_task_logic(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Расширенная логика выполнения задачи"""
        
        # Определить приоритет задачи
        task_priority = self._determine_task_priority(task_description)
        
        # Проверить ограничения ресурсов
        if not await self._check_resource_availability(task_priority):
            return {
                "success": False,
                "error": "Недостаточно ресурсов для выполнения задачи с приоритетом",
                "priority": task_priority
            }
        
        # Выполнить базовую логику
        result = await super()._execute_task_logic(task_description, context)
        
        # Обновить статистику выполнения
        await self._update_execution_stats(task_description, result)
        
        return result
    
    def _determine_task_priority(self, task_description: str) -> str:
        """Определить приоритет задачи"""
        desc_lower = task_description.lower()
        
        # Определить приоритет на основе ключевых слов
        if any(keyword in desc_lower for keyword in ["срочн", "emergency", "critical", "urgent"]):
            return "critical"
        elif any(keyword in desc_lower for keyword in ["важн", "important", "high"]):
            return "high"
        elif any(keyword in desc_lower for keyword in ["обычн", "normal", "medium"]):
            return "medium"
        else:
            return "low"
    
    async def _check_resource_availability(self, priority: str) -> bool:
        """Проверить доступность ресурсов для задачи с приоритетом"""
        # В реальной реализации здесь будет проверка доступных ресурсов
        # В зависимости от приоритета задачи
        return True
    
    async def _update_execution_stats(self, task_description: str, result: Dict[str, Any]):
        """Обновить статистику выполнения"""
        # В реальной реализации здесь будет обновление статистики
        # выполнения задач для анализа производительности
        pass
```

### 2. Создание специфической системы событий

Для адаптации системы событий под специфические нужды:

```python
class CustomEventBus(EventBus):
    """Специфическая шина событий с дополнительными возможностями"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self._event_filters = []
        self._event_processors = []
        self._event_log = []
        self._max_log_size = self.config.get("max_log_size", 1000)
        
        # Инициализировать фильтры и процессоры событий
        self._setup_event_processing()
    
    def _setup_event_processing(self):
        """Настроить обработку событий"""
        # Добавить фильтры событий
        if self.config.get("filter_sensitive_events", True):
            self._event_filters.append(self._filter_sensitive_data)
        
        # Добавить процессоры событий
        if self.config.get("enable_logging", True):
            self._event_processors.append(self._log_event)
        
        if self.config.get("enable_monitoring", True):
            self._event_processors.append(self._monitor_event)
    
    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """Расширенная публикация события с фильтрацией и обработкой"""
        
        # Применить фильтры
        filtered_data = data.copy()
        for filter_func in self._event_filters:
            filtered_data = filter_func(event_type, filtered_data)
            if filtered_data is None:
                # Событие отфильтровано, не публиковать
                return
        
        # Применить процессоры
        processed_data = filtered_data.copy()
        for processor_func in self._event_processors:
            processed_data = await processor_func(event_type, processed_data)
        
        # Вызов базовой реализации
        await super().publish(event_type, processed_data)
    
    def _filter_sensitive_data(self, event_type: EventType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Фильтровать чувствительные данные из события"""
        if not data:
            return data
        
        filtered_data = data.copy()
        
        # Удалить чувствительные поля
        sensitive_fields = ["password", "token", "api_key", "secret"]
        for field in sensitive_fields:
            if field in filtered_data:
                filtered_data[field] = "***FILTERED***"
        
        # Фильтровать вложенные структуры
        for key, value in filtered_data.items():
            if isinstance(value, dict):
                filtered_data[key] = self._filter_sensitive_data(event_type, value)
        
        return filtered_data
    
    async def _log_event(self, event_type: EventType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Залогировать событие"""
        event_entry = {
            "timestamp": time.time(),
            "event_type": event_type.value,
            "data": data,
            "size": len(str(data))
        }
        
        self._event_log.append(event_entry)
        
        # Ограничить размер лога
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]
        
        return data
    
    async def _monitor_event(self, event_type: EventType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Отслеживать событие для мониторинга"""
        # В реальной реализации здесь будет отправка данных
        # в систему мониторинга (например, Prometheus, Grafana и т.д.)
        pass
    
    def add_event_filter(self, filter_func: Callable):
        """Добавить фильтр событий"""
        self._event_filters.append(filter_func)
    
    def add_event_processor(self, processor_func: Callable):
        """Добавить процессор событий"""
        self._event_processors.append(processor_func)
    
    def get_event_log(self, limit: int = None) -> List[Dict[str, Any]]:
        """Получить лог событий"""
        if limit:
            return self._event_log[-limit:]
        return self._event_log
    
    def get_event_stats(self) -> Dict[str, Any]:
        """Получить статистику по событиям"""
        stats = {
            "total_events": len(self._event_log),
            "events_by_type": {},
            "average_event_size": 0
        }
        
        if self._event_log:
            # Подсчитать события по типам
            for entry in self._event_log:
                event_type = entry["event_type"]
                stats["events_by_type"][event_type] = stats["events_by_type"].get(event_type, 0) + 1
            
            # Вычислить средний размер события
            total_size = sum(entry["size"] for entry in self._event_log)
            stats["average_event_size"] = total_size / len(self._event_log)
        
        return stats
```

### 3. Сессионный контекст (Session Context)

Сессионный контекст управляет контекстом выполнения задачи:

```python
class SessionContext:
    """Контекст сессии выполнения задачи"""
    
    def __init__(self, session_id: str, config: Dict[str, Any] = None):
        self.session_id = session_id
        self.config = config or {}
        self.context_data = {}
        self.history = []
        self.metrics = {}
        self.created_at = time.time()
        self.last_accessed = time.time()
        self._max_history_size = self.config.get("max_history_size", 100)
        self._ttl = self.config.get("ttl_seconds", 3600)  # 1 hour default
        
        # Инициализировать метрики
        self.metrics.update({
            "requests_count": 0,
            "errors_count": 0,
            "total_duration": 0,
            "avg_duration": 0
        })
    
    def add_context_data(self, key: str, value: Any):
        """Добавить данные в контекст"""
        self.context_data[key] = value
        self.last_accessed = time.time()
    
    def get_context_data(self, key: str, default=None) -> Any:
        """Получить данные из контекста"""
        self.last_accessed = time.time()
        return self.context_data.get(key, default)
    
    def add_to_history(self, entry: str):
        """Добавить запись в историю"""
        history_entry = {
            "timestamp": time.time(),
            "entry": entry,
            "session_id": self.session_id
        }
        
        self.history.append(history_entry)
        
        # Ограничить размер истории
        if len(self.history) > self._max_history_size:
            self.history = self.history[-self._max_history_size:]
        
        self.last_accessed = time.time()
    
    def update_metric(self, metric_name: str, value: Any):
        """Обновить метрику"""
        self.metrics[metric_name] = value
        self.last_accessed = time.time()
    
    def increment_counter(self, counter_name: str, increment: int = 1):
        """Инкрементировать счетчик"""
        current_value = self.metrics.get(counter_name, 0)
        self.metrics[counter_name] = current_value + increment
        self.last_accessed = time.time()
    
    def add_execution_time(self, duration: float):
        """Добавить время выполнения"""
        self.increment_counter("requests_count")
        self.metrics["total_duration"] += duration
        
        # Обновить среднее время выполнения
        count = self.metrics["requests_count"]
        self.metrics["avg_duration"] = self.metrics["total_duration"] / count
    
    def is_expired(self) -> bool:
        """Проверить, истекло ли время сессии"""
        current_time = time.time()
        return (current_time - self.created_at) > self._ttl
    
    def get_age(self) -> float:
        """Получить возраст сессии в секундах"""
        return time.time() - self.created_at
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить краткую информацию о сессии"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "age_seconds": self.get_age(),
            "expired": self.is_expired(),
            "context_keys": list(self.context_data.keys()),
            "history_count": len(self.history),
            "metrics": self.metrics.copy()
        }
    
    def cleanup_old_sessions(self, sessions_dict: Dict[str, 'SessionContext'], max_sessions: int = 1000):
        """Очистить старые сессии"""
        if len(sessions_dict) <= max_sessions:
            return
        
        # Сортировать сессии по времени последнего доступа
        sorted_sessions = sorted(
            sessions_dict.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Удалить самые старые сессии
        sessions_to_remove = len(sessions_dict) - max_sessions
        for i in range(sessions_to_remove):
            session_id, _ = sorted_sessions[i]
            del sessions_dict[session_id]

class CustomSessionContext(SessionContext):
    """Специфический контекст сессии с дополнительными возможностями"""
    
    def __init__(self, session_id: str, config: Dict[str, Any] = None):
        super().__init__(session_id, config)
        self._data_encryption_enabled = self.config.get("encrypt_data", False)
        self._data_compression_enabled = self.config.get("compress_data", False)
        self._change_log = []
        self._max_change_log_size = self.config.get("max_change_log_size", 50)
        
        # Инициализировать шифрование, если включено
        if self._data_encryption_enabled:
            self._encryption_key = self._generate_encryption_key()
    
    def add_context_data(self, key: str, value: Any):
        """Добавить данные в контекст с дополнительной обработкой"""
        
        # Зашифровать данные, если включено шифрование
        if self._data_encryption_enabled:
            value = self._encrypt_data(value)
        
        # Сжать данные, если включено сжатие
        if self._data_compression_enabled:
            value = self._compress_data(value)
        
        # Вызов базовой реализации
        super().add_context_data(key, value)
        
        # Записать изменение в лог
        self._log_change("add", key, value)
    
    def get_context_data(self, key: str, default=None) -> Any:
        """Получить данные из контекста с дополнительной обработкой"""
        value = super().get_context_data(key, default)
        
        # Расшифровать данные, если они были зашифрованы
        if self._data_encryption_enabled and isinstance(value, str) and value.startswith("ENCRYPTED:"):
            value = self._decrypt_data(value)
        
        # Распаковать данные, если они были сжаты
        if self._data_compression_enabled and isinstance(value, bytes):
            value = self._decompress_data(value)
        
        return value
    
    def _encrypt_data(self, data: Any) -> str:
        """Зашифровать данные"""
        # В реальной реализации здесь будет шифрование данных
        # например, с использованием Fernet или AES
        import json
        serialized_data = json.dumps(data, default=str)
        # Заглушка для шифрования
        return f"ENCRYPTED:{serialized_data}"
    
    def _decrypt_data(self, encrypted_data: str) -> Any:
        """Расшифровать данные"""
        # В реальной реализации здесь будет расшифровка данных
        import json
        encrypted_part = encrypted_data.replace("ENCRYPTED:", "", 1)
        return json.loads(encrypted_part)
    
    def _compress_data(self, data: Any) -> bytes:
        """Сжать данные"""
        # В реальной реализации здесь будет сжатие данных
        # например, с использованием gzip или zlib
        import json
        serialized_data = json.dumps(data, default=str)
        return serialized_data.encode('utf-8')
    
    def _decompress_data(self, compressed_data: bytes) -> Any:
        """Распаковать данные"""
        # В реальной реализации здесь будет распаковка данных
        import json
        serialized_data = compressed_data.decode('utf-8')
        return json.loads(serialized_data)
    
    def _generate_encryption_key(self) -> bytes:
        """Сгенерировать ключ шифрования"""
        # В реальной реализации здесь будет генерация ключа шифрования
        return b"dummy-key-for-demo-purposes-123456"
    
    def _log_change(self, operation: str, key: str, value: Any):
        """Залогировать изменение данных"""
        change_entry = {
            "timestamp": time.time(),
            "operation": operation,
            "key": key,
            "value_preview": str(value)[:50],  # Предварительный просмотр значения
            "session_id": self.session_id
        }
        
        self._change_log.append(change_entry)
        
        # Ограничить размер лога изменений
        if len(self._change_log) > self._max_change_log_size:
            self._change_log = self._change_log[-self._max_change_log_size:]
    
    def get_change_log(self, limit: int = None) -> List[Dict[str, Any]]:
        """Получить лог изменений"""
        if limit:
            return self._change_log[-limit:]
        return self._change_log
```

## Интеграция с системой

### 1. Фабрика ядра

Фабрика для создания специфических компонентов ядра:

```python
class CoreFactory:
    """Фабрика для создания компонентов ядра"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_runtimes = {}
        self._registered_event_buses = {}
        self._registered_session_managers = {}
    
    def register_runtime_type(self, name: str, runtime_class: type):
        """Зарегистрировать тип среды выполнения"""
        self._registered_runtimes[name] = runtime_class
    
    def register_event_bus_type(self, name: str, event_bus_class: type):
        """Зарегистрировать тип шины событий"""
        self._registered_event_buses[name] = event_bus_class
    
    def register_session_manager_type(self, name: str, session_manager_class: type):
        """Зарегистрировать тип менеджера сессий"""
        self._registered_session_managers[name] = session_manager_class
    
    async def create_runtime(
        self, 
        runtime_type: str, 
        initial_state: AgentState, 
        event_publisher: IEventPublisher,
        action_executor: AtomicActionExecutor,
        custom_config: Dict[str, Any] = None
    ) -> IAgentRuntime:
        """Создать среду выполнения"""
        if runtime_type not in self._registered_runtimes:
            raise ValueError(f"Тип среды выполнения '{runtime_type}' не зарегистрирован")
        
        runtime_class = self._registered_runtimes[runtime_type]
        config = {**self.config.get("runtime_defaults", {}), **(custom_config or {})}
        
        runtime = runtime_class(initial_state, event_publisher, action_executor, config)
        await runtime.initialize()
        
        return runtime
    
    async def create_event_bus(self, bus_type: str, custom_config: Dict[str, Any] = None) -> IEventPublisher:
        """Создать шину событий"""
        if bus_type not in self._registered_event_buses:
            raise ValueError(f"Тип шины событий '{bus_type}' не зарегистрирован")
        
        event_bus_class = self._registered_event_buses[bus_type]
        config = {**self.config.get("event_bus_defaults", {}), **(custom_config or {})}
        
        event_bus = event_bus_class(config)
        
        return event_bus
    
    def create_session_context(self, session_id: str, custom_config: Dict[str, Any] = None) -> SessionContext:
        """Создать контекст сессии"""
        config = {**self.config.get("session_defaults", {}), **(custom_config or {})}
        
        # Определить тип сессии на основе конфигурации
        if config.get("custom_features", False):
            return CustomSessionContext(session_id, config)
        else:
            return SessionContext(session_id, config)
```

### 2. Пример использования специфического ядра

```python
# custom_core_usage.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def custom_core_example():
    """Пример использования специфического ядра"""
    
    # Создать фабрику ядра
    core_factory = CoreFactory({
        "runtime_defaults": {
            "memory_limit": "2GB",
            "max_concurrent_tasks": 10
        },
        "event_bus_defaults": {
            "max_log_size": 5000,
            "filter_sensitive_events": True
        },
        "session_defaults": {
            "max_history_size": 200,
            "encrypt_data": True,
            "compress_data": True
        }
    })
    
    # Зарегистрировать специфические типы
    core_factory.register_runtime_type("custom", CustomAgentRuntime)
    core_factory.register_event_bus_type("secure", CustomEventBus)
    
    # Создать компоненты
    event_bus = await core_factory.create_event_bus("secure", {
        "max_log_size": 10000,
        "enable_monitoring": True
    })
    
    # Создать исполнитель атомарных действий
    action_executor = AtomicActionExecutor()
    
    # Создать специфическую среду выполнения
    initial_state = AgentState()
    runtime = await core_factory.create_runtime(
        "custom", 
        initial_state, 
        event_bus, 
        action_executor,
        {
            "memory_manager": {
                "max_memory": "1GB",
                "cleanup_threshold": 0.8
            },
            "context_enhancer": {
                "enable_nlp_enhancement": True,
                "entity_extraction": True
            },
            "task_scheduler": {
                "max_concurrent_tasks": 5,
                "priority_queue_enabled": True
            }
        }
    )
    
    # Создать сессию
    session_context = core_factory.create_session_context(
        "session_12345", 
        {
            "max_history_size": 500,
            "encrypt_data": True,
            "compress_data": False
        }
    )
    
    # Выполнить задачу через специфическую среду
    task_result = await runtime.execute_task(
        task_description="Проанализируй этот Python код на безопасность",
        context={
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python",
            "analysis_type": "security"
        }
    )
    
    print(f"Результат выполнения задачи: {task_result}")
    
    # Получить статистику по событиям
    if hasattr(event_bus, 'get_event_stats'):
        event_stats = event_bus.get_event_stats()
        print(f"Статистика событий: {event_stats}")
    
    # Получить информацию о сессии
    session_summary = session_context.get_summary()
    print(f"Информация о сессии: {session_summary}")
    
    return task_result

# Использование через агентов
async def agent_with_custom_core_example():
    """Пример использования агента с специфическим ядром"""
    
    # Создать фабрику агентов
    agent_factory = AgentFactory()
    
    # Создать агента с использованием специфического ядра
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        core_config={
            "runtime_type": "custom",
            "event_bus_type": "secure",
            "session_config": {
                "encrypt_data": True,
                "max_history_size": 1000
            },
            "runtime_config": {
                "memory_manager": {
                    "max_memory": "2GB"
                }
            }
        }
    )
    
    # Выполнить задачу
    result = await agent.execute_task(
        task_description="Проанализируй безопасность этого кода",
        context={
            "code": "print('Hello, World!')",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения через агента: {result}")
    
    return result
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте компоненты ядра, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые компоненты
class BaseRuntime:
    """Базовая среда выполнения"""
    pass

class EnhancedRuntime(BaseRuntime):
    """Расширенная среда выполнения"""
    pass

class SpecializedRuntime(EnhancedRuntime):
    """Специализированная среда выполнения"""
    pass

# Плохо: монолитные компоненты
class MonolithicRuntime:
    """Монолитная среда выполнения - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и конфиденциальность

Обязательно учитывайте безопасность при расширении ядра:

```python
def _filter_sensitive_data(self, event_type: EventType, data: Dict[str, Any]) -> Dict[str, Any]:
    """Фильтровать чувствительные данные"""
    if not data:
        return data
    
    filtered_data = data.copy()
    
    # Список чувствительных полей
    sensitive_fields = [
        "password", "token", "api_key", "secret", "credentials",
        "credit_card", "ssn", "email", "phone"
    ]
    
    for field in sensitive_fields:
        if field in filtered_data:
            filtered_data[field] = "***FILTERED***"
    
    return filtered_data
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок в расширенных компонентах:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if self.state.error_count > self.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(task_description, context)
        
        # Обновить состояние при успехе
        self.state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except ResourceLimitExceededError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "terminated": True
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }
```

### 4. Тестирование расширенных компонентов

Создавайте тесты для каждого расширенного компонента:

```python
# test_custom_core.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestCustomAgentRuntime:
    @pytest.mark.asyncio
    async def test_custom_runtime_initialization(self):
        """Тест инициализации специфической среды выполнения"""
        # Создание моков зависимостей
        mock_state = AgentState()
        mock_event_publisher = AsyncMock()
        mock_action_executor = AsyncMock()
        
        # Создание специфической среды выполнения
        runtime = CustomAgentRuntime(
            initial_state=mock_state,
            event_publisher=mock_event_publisher,
            action_executor=mock_action_executor,
            custom_config={
                "memory_manager": {"max_memory": "1GB"},
                "context_enhancer": {"enabled": True}
            }
        )
        
        # Проверка инициализации
        assert "memory_manager" in runtime._custom_components
        assert "context_enhancer" in runtime._custom_components
        assert runtime.custom_config["memory_manager"]["max_memory"] == "1GB"
    
    @pytest.mark.asyncio
    async def test_custom_runtime_task_execution(self):
        """Тест выполнения задачи в специфической среде"""
        # Создание моков
        mock_state = AgentState()
        mock_event_publisher = AsyncMock()
        mock_action_executor = AsyncMock()
        
        # Создание среды
        runtime = CustomAgentRuntime(
            initial_state=mock_state,
            event_publisher=mock_event_publisher,
            action_executor=mock_action_executor,
            custom_config={}
        )
        
        # Выполнение задачи
        result = await runtime.execute_task(
            task_description="Тестовая задача",
            context={"test": "data"}
        )
        
        # Проверка результата
        assert "success" in result
        assert result["step"] == 1  # Проверка, что шаг был увеличен

class TestCustomEventBus:
    @pytest.mark.asyncio
    async def test_event_filtering(self):
        """Тест фильтрации событий"""
        event_bus = CustomEventBus({
            "filter_sensitive_events": True,
            "max_log_size": 100
        })
        
        # Тест фильтрации чувствительных данных
        test_data = {
            "normal_field": "value",
            "password": "secret123",
            "api_key": "key123"
        }
        
        # Добавить фильтр и протестировать
        filtered_data = event_bus._filter_sensitive_data(EventType.TASK_STARTED, test_data)
        
        assert filtered_data["normal_field"] == "value"
        assert filtered_data["password"] == "***FILTERED***"
        assert filtered_data["api_key"] == "***FILTERED***"
    
    @pytest.mark.asyncio
    async def test_event_logging(self):
        """Тест логирования событий"""
        event_bus = CustomEventBus({
            "enable_logging": True,
            "max_log_size": 10
        })
        
        # Опубликовать несколько событий
        for i in range(15):  # Больше, чем max_log_size
            await event_bus.publish(EventType.TASK_STARTED, {"test": f"data_{i}"})
        
        # Проверить, что лог ограничен
        event_log = event_bus.get_event_log()
        assert len(event_log) <= 10  # max_log_size
        assert len(event_log) == 10  # Все 10 последних событий
```

Эти примеры показывают, как адаптировать и расширять ядро Composable AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.