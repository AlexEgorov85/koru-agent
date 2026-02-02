# Предложение по рефакторингу core/system_context

## Текущая проблема

Директория `core/system_context` содержит слишком много различных компонентов (фабрики, реестры, шины событий), что может указывать на нарушение принципа единственной ответственности (SRP). Как указано в архитектурной миграции, необходимо "рассмотреть разбиение на более специфические компоненты".

## Анализ текущей структуры

На основе анализа файлов в директории `core/system_context`, выявлены следующие основные функциональности, объединенные в одном модуле:


1. **Фабрики** (`agent_factory.py`, `factory.py`): создание агентов и общих объектов
2. **Обработчики событий** (`agent_step_display_handler.py`, `interfaces.py`): отображение шагов агента, интерфейсы системного контекста
3. **Базовые классы** (`base_system_contex.py`): абстрактные базовые классы
4. **Шина событий** (`event_bus.py`, `event_system.py`): управление событиями и подписками
5. **Реестры** (`capability_registry.py`, `resource_registry.py`, `resource_manager.py`): управление возможностями и ресурсами
6. **Шлюзы** (`database_gateway.py`, `execution_gateway.py`): взаимодействие с внешними системами
7. **Управление** (`lifecycle_manager.py`, `resource_manager.py`): жизненный цикл, ресурсы

## Предлагаемое разбиение

### 1. Поддиректория factories (application слой)

Файлы: `core/application/system_factories/agent_factory.py`, `core/application/system_factories/general_factory.py`

Содержит фабрики для создания различных компонентов системы.


#### agent_factory.py
```python
from typing import Any, Dict, Optional
from core.system_context.interfaces import IAgentFactory
from core.agent_runtime.runtime import AgentRuntime
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext

class AgentFactory(IAgentFactory):
    """
    Фабрика для создания агентов с различными конфигурациями и возможностями.
    """
    
    def __init__(self, system_context: SystemContext):
        self.system_context = system_context
    
    async def create_agent(self, **kwargs) -> AgentRuntime:
        """
        Создание агента с заданными параметрами.
        """
        session_context = kwargs.get('session_context') or SessionContext()
        return AgentRuntime(
            system_context=self.system_context,
            session_context=session_context,
            **kwargs
        )
    
    async def create_agent_for_question(self, question: str, **kwargs) -> AgentRuntime:
        """
        Создание агента, настроенного под конкретный вопрос или задачу.
        """
        # Определяем домен задачи и адаптируем агента
        domain_info = self.system_context.domain_manager.classify_task(question)
        adapter = self.system_context.task_adapter.adapt_to_task(question)
        
        kwargs['domain'] = domain_info.get('primary_domain', 'general')
        kwargs['thinking_pattern'] = adapter.get('pattern', 'react_composable')
        kwargs['goal'] = question
        
        return await self.create_agent(**kwargs)
```

#### general_factory.py
```python
from typing import Type, Any, Dict, Optional, TypeVar
from core.system_context.interfaces import IFactory
from core.system_context.system_context import SystemContext

T = TypeVar('T')

class GeneralFactory(IFactory):
    """
    Общая фабрика для создания различных объектов системы.
    """
    
    def __init__(self, system_context: SystemContext):
        self.system_context = system_context
    
    def create_instance(self, cls: Type[T], **kwargs) -> T:
        """
        Создание экземпляра класса с внедрением зависимостей из системного контекста.
        """
        # Автоматическое внедрение системного контекста если требуется
        if 'system_context' not in kwargs:
            kwargs['system_context'] = self.system_context
            
        return cls(**kwargs)
    
    def create_from_config(self, config_key: str, **override_kwargs) -> Any:
        """
        Создание объекта на основе конфигурации из системного контекста.
        """
        config = self.system_context.get_config(config_key)
        if config:
            config.update(override_kwargs)
            class_path = config.pop('class_path')
            # Динамический импорт класса
            module_path, class_name = class_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            return self.create_instance(cls, **config)
        else:
            raise ValueError(f"Configuration not found for key: {config_key}")
```

### 2. Поддиректория event_system (infrastructure слой)

Файлы: `core/infrastructure/event_system/event_bus.py`, `core/infrastructure/event_system/event_system.py`, `core/infrastructure/event_system/interfaces.py`

Содержит компоненты для управления событиями и подписками.


#### event_bus.py
```python
import asyncio
from typing import Dict, List, Callable, Any, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Типы событий в системе."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    USER_INTERACTION = "user_interaction"
    AGENT_STEP = "agent_step"


@dataclass
class Event:
    """Представление события."""
    event_type: EventType
    source: str
    data: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class IEventHandler(Protocol):
    """Интерфейс обработчика событий."""
    async def handle(self, event: Event) -> None: ...


class EventBus:
    """Центральная шина событий системы."""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[IEventHandler]] = {}
        self._global_handlers: List[IEventHandler] = []
        # Инициализация для всех типов событий
        for event_type in EventType:
            self._handlers[event_type] = []
    
    async def publish(self, event: Event) -> None:
        """Публикация события."""
        # Обработка глобальными обработчиками
        for handler in self._global_handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
        
        # Обработка специфичными обработчиками
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type}: {e}")
    
    def subscribe(self, event_type: EventType, handler: IEventHandler) -> None:
        """Подписка на тип события."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def subscribe_global(self, handler: IEventHandler) -> None:
        """Глобальная подписка на все события."""
        self._global_handlers.append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: IEventHandler) -> bool:
        """Отписка от типа события."""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            return True
        return False
```

#### event_system.py
```python
from typing import Dict, Any
from core.infrastructure.event_system.event_bus import EventBus, Event, EventType, IEventHandler
from core.system_context.system_context import SystemContext

class EventSystem:
    """
    Система управления событиями с интеграцией в системный контекст.
    """
    
    def __init__(self, system_context: SystemContext):
        self.system_context = system_context
        self.event_bus = EventBus()
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Настройка стандартных обработчиков событий."""
        # Обработчик логирования
        logging_handler = LoggingEventHandler(self.system_context)
        self.event_bus.subscribe_global(logging_handler)
        
        # Обработчик отображения шагов агента
        step_display_handler = AgentStepDisplayHandler(self.system_context)
        self.event_bus.subscribe(EventType.AGENT_STEP, step_display_handler)
    
    async def emit(self, event_type: EventType, source: str, data: Dict[str, Any]) -> None:
        """Генерация события."""
        event = Event(event_type=event_type, source=source, data=data)
        await self.event_bus.publish(event)
    
    def on(self, event_type: EventType, handler: IEventHandler) -> None:
        """Подписка на событие."""
        self.event_bus.subscribe(event_type, handler)
    
    def on_any(self, handler: IEventHandler) -> None:
        """Подписка на все события."""
        self.event_bus.subscribe_global(handler)


class LoggingEventHandler(IEventHandler):
    """Обработчик событий для логирования."""
    
    def __init__(self, system_context: SystemContext):
        self.system_context = system_context
        import logging
        self.logger = logging.getLogger(__name__)
    
    async def handle(self, event: Event) -> None:
        """Обработка события логирования."""
        log_msg = f"[{event.source}] {event.event_type.value}: {event.data}"
        if event.event_type == EventType.ERROR:
            self.logger.error(log_msg)
        elif event.event_type == EventType.WARNING:
            self.logger.warning(log_msg)
        elif event.event_type == EventType.INFO:
            self.logger.info(log_msg)
        elif event.event_type == EventType.DEBUG:
            self.logger.debug(log_msg)
        else:
            self.logger.info(log_msg)
```

### 3. Поддиректория registries (application слой)

Файлы: `core/application/system_registries/capability_registry.py`, `core/application/system_registries/resource_registry.py`, `core/application/system_registries/interfaces.py`

Содержит компоненты для управления реестрами возможностей и ресурсов.


#### capability_registry.py
```python
from typing import Dict, List, Optional, Protocol
from dataclasses import dataclass
from core.system_context.interfaces import ICapabilityRegistry

@dataclass
class CapabilityInfo:
    """Информация о возможностях системы."""
    name: str
    description: str
    category: str
    parameters_schema: Optional[Dict] = None
    dependencies: Optional[List[str]] = None


class ICapabilityRegistry(Protocol):
    """Интерфейс реестра возможностей."""
    async def register_capability(self, capability_info: CapabilityInfo) -> bool: ...
    async def unregister_capability(self, name: str) -> bool: ...
    async def get_capability(self, name: str) -> Optional[CapabilityInfo]: ...
    async def list_capabilities(self, category: str = None) -> List[CapabilityInfo]: ...
    async def has_capability(self, name: str) -> bool: ...


class CapabilityRegistry(ICapabilityRegistry):
    """Реестр возможностей системы."""
    
    def __init__(self):
        self._capabilities: Dict[str, CapabilityInfo] = {}
        self._categories: Dict[str, List[str]] = {}
    
    async def register_capability(self, capability_info: CapabilityInfo) -> bool:
        """Регистрация возможности."""
        if capability_info.name in self._capabilities:
            return False  # Уже существует
        
        self._capabilities[capability_info.name] = capability_info
        
        # Добавление в категорию
        if capability_info.category not in self._categories:
            self._categories[capability_info.category] = []
        self._categories[capability_info.category].append(capability_info.name)
        return True
    
    async def unregister_capability(self, name: str) -> bool:
        """Удаление возможности."""
        if name not in self._capabilities:
            return False
        
        cap_info = self._capabilities[name]
        del self._capabilities[name]
        
        # Удаление из категории
        if cap_info.category in self._categories:
            if name in self._categories[cap_info.category]:
                self._categories[cap_info.category].remove(name)
        return True
    
    async def get_capability(self, name: str) -> Optional[CapabilityInfo]:
        """Получение информации о возможности."""
        return self._capabilities.get(name)
    
    async def list_capabilities(self, category: str = None) -> List[CapabilityInfo]:
        """Получение списка возможностей."""
        if category:
            if category not in self._categories:
                return []
            names = self._categories[category]
            return [self._capabilities[name] for name in names]
        else:
            return list(self._capabilities.values())
    
    async def has_capability(self, name: str) -> bool:
        """Проверка наличия возможности."""
        return name in self._capabilities
```

#### resource_registry.py
```python
from typing import Dict, List, Optional, Protocol, Any, Type
from dataclasses import dataclass
from core.system_context.interfaces import IResourceRegistry

@dataclass
class ResourceInfo:
    """Информация о ресурсе."""
    name: str
    resource_type: str
    instance: Any
    is_singleton: bool = True
    dependencies: Optional[List[str]] = None


class IResourceRegistry(Protocol):
    """Интерфейс реестра ресурсов."""
    async def register_resource(self, resource_info: ResourceInfo) -> bool: ...
    async def unregister_resource(self, name: str) -> bool: ...
    async def get_resource(self, name: str) -> Optional[Any]: ...
    async def get_resource_by_type(self, resource_type: str) -> List[Any]: ...
    async def list_resources(self, resource_type: str = None) -> List[str]: ...
    async def has_resource(self, name: str) -> bool: ...


class ResourceRegistry(IResourceRegistry):
    """Реестр ресурсов системы."""
    
    def __init__(self):
        self._resources: Dict[str, ResourceInfo] = {}
        self._types: Dict[str, List[str]] = {}
    
    async def register_resource(self, resource_info: ResourceInfo) -> bool:
        """Регистрация ресурса."""
        if resource_info.name in self._resources:
            return False  # Уже существует
        
        self._resources[resource_info.name] = resource_info
        
        # Добавление в тип
        if resource_info.resource_type not in self._types:
            self._types[resource_info.resource_type] = []
        self._types[resource_info.resource_type].append(resource_info.name)
        return True
    
    async def unregister_resource(self, name: str) -> bool:
        """Удаление ресурса."""
        if name not in self._resources:
            return False
        
        res_info = self._resources[name]
        del self._resources[name]
        
        # Удаление из типа
        if res_info.resource_type in self._types:
            if name in self._types[res_info.resource_type]:
                self._types[res_info.resource_type].remove(name)
        return True
    
    async def get_resource(self, name: str) -> Optional[Any]:
        """Получение ресурса."""
        resource_info = self._resources.get(name)
        if resource_info and resource_info.is_singleton:
            return resource_info.instance
        elif resource_info:
            # Для не-синглтонов создаем новый экземпляр
            resource_class = type(resource_info.instance)
            return resource_class(**getattr(resource_info.instance, '__dict__', {}))
    
    async def get_resource_by_type(self, resource_type: str) -> List[Any]:
        """Получение ресурсов по типу."""
        if resource_type not in self._types:
            return []
        names = self._types[resource_type]
        return [await self.get_resource(name) for name in names]
    
    async def list_resources(self, resource_type: str = None) -> List[str]:
        """Получение списка ресурсов."""
        if resource_type:
            if resource_type not in self._types:
                return []
            return self._types[resource_type][:]
        else:
            return list(self._resources.keys())
    
    async def has_resource(self, name: str) -> bool:
        """Проверка наличия ресурса."""
        return name in self._resources
```

### 4. Поддиректория gateways (infrastructure слой)

Файлы: `core/infrastructure/gateways/database_gateway.py`, `core/infrastructure/gateways/execution_gateway.py`, `core/infrastructure/gateways/interfaces.py`

Содержит шлюзы для взаимодействия с внешними системами.


#### database_gateway.py
```python
from typing import Any, Dict, List, Optional, Protocol
from core.system_context.interfaces import IDatabaseGateway

class IDatabaseGateway(Protocol):
    """Интерфейс шлюза базы данных."""
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]: ...
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> int: ...
    async def get_connection_info(self) -> Dict[str, Any]: ...


class DatabaseGateway(IDatabaseGateway):
    """Шлюз для взаимодействия с базами данных."""
    
    def __init__(self, connection_string: str, provider_name: str = "default"):
        self.connection_string = connection_string
        self.provider_name = provider_name
        self._connection = None
        self._validate_connection_string()
    
    def _validate_connection_string(self) -> None:
        """Проверка строки подключения."""
        if not self.connection_string or not isinstance(self.connection_string, str):
            raise ValueError("Connection string must be a valid string")
        if "://" not in self.connection_string:
            raise ValueError("Connection string must contain protocol specification")
    
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Выполнение SQL-запроса и возврат результата."""
        if not self._connection:
            await self._connect()
        params = params or {}
        # Выполнение запроса с параметрами
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        # Преобразование результата в список словарей
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> int:
        """Выполнение команды (INSERT, UPDATE, DELETE) и возврат количества измененных строк."""
        if not self._connection:
            await self._connect()
        params = params or {}
        cursor = await self._connection.execute(command, params)
        await self._connection.commit()
        return cursor.rowcount
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Получение информации о подключении."""
        if not self._connection:
            return {
                "connected": False,
                "provider": self.provider_name,
                "connection_string": self.connection_string
            }
        return {
            "connected": True,
            "provider": self.provider_name,
            "connection_string": self.connection_string,
            "server_info": await self._get_server_info()
        }
    
    async def _connect(self) -> None:
        """Установление подключения к базе данных."""
        # Используем фабрику провайдеров для получения нужного провайдера
        from core.infrastructure.providers.database_provider_factory import DatabaseProviderFactory
        factory = DatabaseProviderFactory()
        self._connection = await factory.create_provider(self.connection_string, self.provider_name)
    
    async def _get_server_info(self) -> Dict[str, Any]:
        """Получение информации о сервере базы данных."""
        # Реализация получения информации специфична для провайдера
        # Возвращаем базовую информацию
        return {"server_version": "unknown", "driver": "asyncpg" if "postgresql" in self.connection_string else "other"}
```

#### execution_gateway.py
```python
from typing import Any, Dict, Optional, Protocol
from core.system_context.interfaces import IExecutionGateway

class IExecutionGateway(Protocol):
    """Интерфейс шлюза выполнения."""
    async def execute_function(self, func, *args, **kwargs) -> Any: ...
    async def execute_method(self, obj, method_name: str, *args, **kwargs) -> Any: ...
    async def execute_capability(self, capability_name: str, parameters: Dict[str, Any]) -> Any: ...


class ExecutionGateway(IExecutionGateway):
    """Шлюз для выполнения различных операций и вызова возможностей."""
    
    def __init__(self, system_context):
        self.system_context = system_context
        self._capability_registry = system_context.get_capability_registry()
    
    async def execute_function(self, func, *args, **kwargs) -> Any:
        """Выполнение функции с безопасной оберткой."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Для синхронных функций используем thread pool executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        except Exception as e:
            raise ExecutionError(f"Error executing function {func.__name__}: {str(e)}")
    
    async def execute_method(self, obj, method_name: str, *args, **kwargs) -> Any:
        """Выполнение метода объекта."""
        if not hasattr(obj, method_name):
            raise AttributeError(f"Object {type(obj).__name__} has no method {method_name}")
        
        method = getattr(obj, method_name)
        if not callable(method):
            raise TypeError(f"Attribute {method_name} of object {type(obj).__name__} is not callable")
        
        return await self.execute_function(method, *args, **kwargs)
    
    async def execute_capability(self, capability_name: str, parameters: Dict[str, Any]) -> Any:
        """Выполнение зарегистрированной возможности."""
        capability = await self._capability_registry.get_capability(capability_name)
        if not capability:
            raise CapabilityNotFoundError(f"Capability '{capability_name}' not found")
        
        # Здесь мы должны получить экземпляр самой возможности из реестра ресурсов
        # или другим способом
        capability_instance = await self.system_context.get_resource(capability_name)
        if not capability_instance:
            raise CapabilityInstanceError(f"No instance found for capability '{capability_name}'")
        
        # Выполняем возможность с параметрами
        return await self.execute_method(capability_instance, "execute", parameters)
    
    async def execute_code_block(self, code: str, globals_dict: Dict[str, Any] = None, locals_dict: Dict[str, Any] = None) -> Any:
        """Выполнение блока кода с безопасной изоляцией."""
        # Для безопасности ограничиваем выполнение кода
        safe_globals = {
            "__builtins__": {
                "len": len, "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set, "range": range,
                "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
                "print": print, "min": min, "max": max, "sum": sum, "abs": abs
            }
        }
        if globals_dict:
            safe_globals.update(globals_dict)
        safe_locals = locals_dict or {}
        
        exec(code, safe_globals, safe_locals)
        # Возвращаем результат последнего выражения (если он есть)
        if safe_locals and "__result__" in safe_locals:
            return safe_locals["__result__"]
        return safe_locals
```

### 5. Поддиректория managers (application слой)

Файлы: `core/application/system_managers/lifecycle_manager.py`, `core/application/system_managers/resource_manager.py`, `core/application/system_managers/interfaces.py`

Содержит компоненты управления жизненным циклом и ресурсами.


#### lifecycle_manager.py
```python
from typing import Dict, List, Protocol, Optional, Any
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LifecyclePhase(Enum):
    """Фазы жизненного цикла системы."""
    INITIALIZATION = "initialization"
    CONFIGURATION = "configuration"
    STARTUP = "startup"
    RUNNING = "running"
    SHUTDOWN = "shutdown"
    TERMINATED = "terminated"


class ILifecycleManager(Protocol):
    """Интерфейс менеджера жизненного цикла."""
    async def initialize(self) -> bool: ...
    async def startup(self) -> bool: ...
    async def shutdown(self) -> None: ...
    async def get_status(self) -> Dict[str, Any]: ...
    async def register_component(self, name: str, initializer, finalizer) -> bool: ...


class LifecycleManager(ILifecycleManager):
    """Менеджер жизненного цикла системы."""
    
    def __init__(self):
        self.phase = LifecyclePhase.INITIALIZATION
        self.components: Dict[str, Dict[str, Any]] = {}
        self.initialization_order: List[str] = []
        self.shutdown_order: List[str] = []
        self._start_time: Optional[datetime] = None
    
    async def initialize(self) -> bool:
        """Инициализация всех зарегистрированных компонентов."""
        if self.phase != LifecyclePhase.INITIALIZATION:
            return False
        
        logger.info("Starting system initialization...")
        self._start_time = datetime.now()
        
        success = True
        for component_name in self.initialization_order:
            component = self.components[component_name]
            try:
                init_func = component['initializer']
                if init_func:
                    if asyncio.iscoroutinefunction(init_func):
                        result = await init_func()
                    else:
                        result = init_func()
                    if result is False:
                        logger.error(f"Initialization failed for component: {component_name}")
                        success = False
                component['initialized'] = True
                logger.debug(f"Component {component_name} initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing component {component_name}: {e}")
                success = False
                component['initialized'] = False
        
        if success:
            self.phase = LifecyclePhase.CONFIGURATION
            logger.info("System initialization completed successfully")
        else:
            logger.error("System initialization failed")
        return success
    
    async def startup(self) -> bool:
        """Запуск системы."""
        if self.phase != LifecyclePhase.CONFIGURATION:
            return False
        
        logger.info("Starting system startup sequence...")
        self.phase = LifecyclePhase.STARTUP
        
        success = True
        # Здесь можно выполнить дополнительные действия при запуске
        # например, запуск фоновых задач, сервисов и т.д.
        self.phase = LifecyclePhase.RUNNING
        logger.info("System started successfully")
        return success
    
    async def shutdown(self) -> None:
        """Завершение работы системы."""
        if self.phase == LifecyclePhase.SHUTDOWN or self.phase == LifecyclePhase.TERMINATED:
            return  # Уже завершаемся или завершены
        
        logger.info("Starting system shutdown...")
        self.phase = LifecyclePhase.SHUTDOWN
        
        # Завершение компонентов в обратном порядке инициализации
        for component_name in reversed(self.shutdown_order):
            component = self.components[component_name]
            try:
                finalizer = component.get('finalizer')
                if finalizer:
                    if asyncio.iscoroutinefunction(finalizer):
                        await finalizer()
                    else:
                        finalizer()
                logger.debug(f"Component {component_name} finalized")
            except Exception as e:
                logger.error(f"Error finalizing component {component_name}: {e}")
        
        self.phase = LifecyclePhase.TERMINATED
        logger.info("System shutdown completed")
    
    async def get_status(self) -> Dict[str, Any]:
        """Получение статуса системы."""
        return {
            "phase": self.phase.value,
            "uptime": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            "components_count": len(self.components),
            "initialized_components": len([c for c in self.components.values() if c.get('initialized', False)])
        }
    
    async def register_component(self, name: str, initializer=None, finalizer=None, depends_on: List[str] = None) -> bool:
        """Регистрация компонента с указанием зависимостей."""
        if name in self.components:
            return False  # Компонент уже зарегистрирован
        
        self.components[name] = {
            'initializer': initializer,
            'finalizer': finalizer,
            'depends_on': depends_on or [],
            'initialized': False
        }
        
        # Добавляем в порядке инициализации с учетом зависимостей
        self._insert_component_in_order(name, self.initialization_order, depends_on)
        # Для завершения в обратном порядке
        self._insert_component_in_order(name, self.shutdown_order, depends_on, reverse=True)
        return True
    
    def _insert_component_in_order(self, name: str, order_list: List[str], depends_on: List[str], reverse: bool = False):
        """Вставка компонента в список с учетом зависимостей."""
        if not depends_on:
            if reverse:
                order_list.insert(0, name)
            else:
                order_list.append(name)
        else:
            # Находим позицию для вставки после всех зависимостей
            pos = len(order_list)
            for dep in depends_on:
                if dep in order_list:
                    dep_pos = order_list.index(dep)
                    if dep_pos < pos:
                        pos = dep_pos
            if reverse:
                # При обратном порядке зависимые идут раньше
                order_list.insert(pos, name)
            else:
                # При прямом порядке зависимые идут позже (вставляем после последней зависимости)
                order_list.insert(pos + 1, name)
```

#### resource_manager.py
```python
from typing import Dict, Any, Optional, Protocol, List
from core.application.system_registries.resource_registry import ResourceRegistry, ResourceInfo

class IResourceManager(Protocol):
    """Интерфейс менеджера ресурсов."""
    async def acquire_resource(self, name: str) -> Optional[Any]: ...
    async def release_resource(self, name: str) -> bool: ...
    async def get_resource_usage(self) -> Dict[str, Any]: ...
    async def cleanup_unused_resources(self) -> int: ...


class ResourceManager(IResourceManager):
    """Менеджер ресурсов системы."""
    
    def __init__(self, resource_registry: ResourceRegistry):
        self.resource_registry = resource_registry
        self._active_resources: Dict[str, Any] = {}
        self._resource_usage: Dict[str, Dict[str, Any]] = {}
        self._acquisition_times: Dict[str, float] = {}
    
    async def acquire_resource(self, name: str) -> Optional[Any]:
        """Получение ресурса для использования."""
        resource = await self.resource_registry.get_resource(name)
        if resource:
            self._active_resources[name] = resource
            self._acquisition_times[name] = asyncio.get_event_loop().time()
            # Обновляем статистику использования
            if name not in self._resource_usage:
                self._resource_usage[name] = {"acquired_count": 0, "released_count": 0}
            self._resource_usage[name]["acquired_count"] += 1
        return resource
    
    async def release_resource(self, name: str) -> bool:
        """Освобождение ресурса."""
        if name in self._active_resources:
            del self._active_resources[name]
            if name in self._acquisition_times:
                del self._acquisition_times[name]
            if name in self._resource_usage:
                self._resource_usage[name]["released_count"] += 1
            return True
        return False
    
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Получение информации об использовании ресурсов."""
        active_count = len(self._active_resources)
        total_acquired = sum(info.get("acquired_count", 0) for info in self._resource_usage.values())
        total_released = sum(info.get("released_count", 0) for info in self._resource_usage.values())
        return {
            "active_resources": active_count,
            "total_acquired": total_acquired,
            "total_released": total_released,
            "resource_details": self._resource_usage.copy(),
            "active_resource_names": list(self._active_resources.keys())
        }
    
    async def cleanup_unused_resources(self) -> int:
        """Очистка неиспользуемых ресурсов."""
        # В простой реализации освобождаем все активные ресурсы
        # В реальной системе можно добавить логику определения неиспользуемых ресурсов
        # например, по времени последнего использования
        released_count = 0
        for name in list(self._active_resources.keys()):
            if await self.release_resource(name):
                released_count += 1
        return released_count
```

### 6. Интерфейсы (config слой)

Файл: `core/config/system_interfaces/interfaces.py`

Содержит общие интерфейсы для системного контекста.


```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

# Интерфейсы для фабрик
class IAgentFactory(Protocol):
    """Интерфейс фабрики агентов."""
    async def create_agent(self, **kwargs) -> Any: ...
    async def create_agent_for_question(self, question: str, **kwargs) -> Any: ...

class IFactory(Protocol):
    """Общий интерфейс фабрики."""
    def create_instance(self, cls, **kwargs) -> Any: ...
    def create_from_config(self, config_key: str, **override_kwargs) -> Any: ...

# Интерфейсы для реестров
class ICapabilityRegistry(Protocol):
    """Интерфейс реестра возможностей."""
    async def register_capability(self, name: str, capability: Any) -> bool: ...
    async def get_capability(self, name: str) -> Optional[Any]: ...
    async def list_capabilities(self) -> List[str]: ...

class IResourceRegistry(Protocol):
    """Интерфейс реестра ресурсов."""
    async def register_resource(self, name: str, resource: Any) -> bool: ...
    async def get_resource(self, name: str) -> Optional[Any]: ...
    async def list_resources(self) -> List[str]: ...

# Интерфейсы для шлюзов
class IDatabaseGateway(Protocol):
    """Интерфейс шлюза базы данных."""
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]: ...
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> int: ...

class IExecutionGateway(Protocol):
    """Интерфейс шлюза выполнения."""
    async def execute_function(self, func, *args, **kwargs) -> Any: ...
    async def execute_capability(self, capability_name: str, parameters: Dict[str, Any]) -> Any: ...

# Интерфейсы для менеджеров
class ILifecycleManager(Protocol):
    """Интерфейс менеджера жизненного цикла."""
    async def initialize(self) -> bool: ...
    async def startup(self) -> bool: ...
    async def shutdown(self) -> None: ...

class IResourceManager(Protocol):
    """Интерфейс менеджера ресурсов."""
    async def acquire_resource(self, name: str) -> Optional[Any]: ...
    async def release_resource(self, name: str) -> bool: ...
```

### 7. Основной системный контекст (application слой)

Файл: `core/application/system_context/system_context.py`

Обновленная реализация системного контекста, использующая все новые компоненты.


```python
from typing import Any, Dict, Optional
from core.system_context.base_system_contex import BaseSystemContext
from core.application.system_factories.agent_factory import AgentFactory
from core.application.system_registries.capability_registry import CapabilityRegistry
from core.application.system_managers.lifecycle_manager import LifecycleManager
from core.infrastructure.event_system.event_system import EventSystem
from core.infrastructure.gateways.database_gateway import DatabaseGateway
from core.infrastructure.gateways.execution_gateway import ExecutionGateway

class SystemContext(BaseSystemContext):
    """
    Реализация системного контекста с разделенными ответственностями.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.agent_factory = AgentFactory(self)
        self.capability_registry = CapabilityRegistry()
        self.lifecycle_manager = LifecycleManager()
        self.event_system = EventSystem(self)
        self.database_gateway = DatabaseGateway(
            self.config.get("database_url", "sqlite:///default.db"),
            self.config.get("database_provider", "default")
        )
        self.execution_gateway = ExecutionGateway(self)
        self.resource_manager = ResourceManager(self.get_resource_registry())
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Инициализация системного контекста."""
        # Регистрируем основные компоненты в менеджере жизненного цикла
        await self.lifecycle_manager.register_component(
            "event_system", 
            initializer=self.event_system._setup_default_handlers
        )
        await self.lifecycle_manager.register_component(
            "database_gateway",
            initializer=self.database_gateway._connect
        )
        # Другие компоненты...
        success = await self.lifecycle_manager.initialize()
        if success:
            self.initialized = True
        return success
    
    async def shutdown(self) -> None:
        """Завершение системного контекста."""
        await self.lifecycle_manager.shutdown()
        self.initialized = False
    
    def get_agent_factory(self):
        """Получение фабрики агентов."""
        return self.agent_factory
    
    def get_capability_registry(self):
        """Получение реестра возможностей."""
        return self.capability_registry
    
    def get_event_system(self):
        """Получение системы событий."""
        return self.event_system
    
    def get_database_gateway(self):
        """Получение шлюза базы данных."""
        return self.database_gateway
    
    def get_execution_gateway(self):
        """Получение шлюза выполнения."""
        return self.execution_gateway
    
    def get_resource_manager(self):
        """Получение менеджера ресурсов."""
        return self.resource_manager
    
    # Реализация абстрактных методов BaseSystemContext
    def get_resource(self, name: str) -> Optional[Any]:
        """Получение ресурса по имени."""
        return self.resource_manager.acquire_resource(name)
    
    async def call_llm(self, prompt: str) -> str:
        """Вызов LLM."""
        # Используем шлюз выполнения для вызова соответствующего capability
        result = await self.execution_gateway.execute_capability("llm_call", {"prompt": prompt})
        return result if isinstance(result, str) else str(result)
    
    async def create_agent(self, **kwargs):
        """Создание агента."""
        return await self.agent_factory.create_agent(**kwargs)
    
    async def create_agent_for_question(self, question: str, **kwargs):
        """Создание агента для конкретного вопроса."""
        return await self.agent_factory.create_agent_for_question(question, **kwargs)
    
    async def execute_sql_query(self, query: str, params: dict = None, db_provider_name: str = "default"):
        """Выполнение SQL-запроса."""
        return await self.database_gateway.execute_query(query, params)
    
    async def call_llm_with_params(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        llm_provider_name: str = "default",
        **kwargs
    ):
        """Вызов LLM с параметрами."""
        params = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        return await self.execution_gateway.execute_capability("llm_call_with_params", params)
    
    async def run_skill(self, skill_name: str, capability_name: str, parameters: dict, session_context = None):
        """Выполнение навыка."""
        # Получаем навык из реестра ресурсов
        skill = await self.get_resource(skill_name)
        if skill and hasattr(skill, capability_name):
            method = getattr(skill, capability_name)
            return await self.execution_gateway.execute_function(method, **parameters)
        else:
            raise ValueError(f"Skill {skill_name} with capability {capability_name} not found")
```

## Преимущества рефакторинга

1. **Разделение ответственностей**: Каждый компонент теперь сосредоточен на одной функции
2. **Улучшенная тестируемость**: Компоненты можно тестировать изолированно
3. **Лучшая поддержка**: Изменения в одном компоненте не влияют на другие
4. **Соблюдение принципов SOLID**: Особенно SRP (Single Responsibility Principle) и ISP (Interface Segregation Principle)
5. **Более четкая архитектура**: Соответствие Clean Architecture с четким разделением на слои и поддиректории

## План миграции

1. Создать новые поддиректории с новой структурой
2. Перенести соответствующие файлы в новые директории
3. Обновить все импорты в проекте, чтобы использовать новые пути
4. Обновить документацию архитектуры
5. Проверить работоспособность системы после изменений