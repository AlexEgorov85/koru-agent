"""
Контейнер для внедрения зависимостей (Dependency Injection).

АРХИТЕКТУРА:
- Регистрация реализаций интерфейсов
- Разрешение зависимостей по типу
- Управление временем жизни (singleton, transient, scoped)

USAGE:
```python
from core.di.container import DependencyContainer
from core.interfaces import DatabaseInterface, LLMInterface

container = DependencyContainer()

# Регистрация
container.register_singleton(DatabaseInterface, postgresql_provider)
container.register_singleton(LLMInterface, llama_provider)

# Разрешение
db = container.resolve(DatabaseInterface)
llm = container.resolve(LLMInterface)
```
"""

from typing import Dict, Type, Any, Optional, Callable, List, Generic, TypeVar
from enum import Enum
from core.infrastructure.logging import EventBusLogger


class ServiceLifetime(Enum):
    """Время жизни службы."""
    SINGLETON = "singleton"  # Один экземпляр для всех
    TRANSIENT = "transient"  # Новый экземпляр при каждом запросе
    SCOPED = "scoped"        # Один экземпляр в рамках scope


T = TypeVar('T')


class ServiceDescriptor(Generic[T]):
    """Дескриптор службы для регистрации в контейнере."""
    
    def __init__(
        self,
        interface: Type[T],
        implementation: Optional[T] = None,
        factory: Optional[Callable[[], T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON
    ):
        self.interface = interface
        self._implementation = implementation
        self._factory = factory
        self.lifetime = lifetime
        self._instance: Optional[T] = None
    
    def get_instance(self, container: 'DependencyContainer') -> T:
        """Получить экземпляр службы."""
        if self.lifetime == ServiceLifetime.SINGLETON:
            if self._instance is None:
                self._instance = self._create_instance(container)
            return self._instance
        
        elif self.lifetime == ServiceLifetime.TRANSIENT:
            return self._create_instance(container)
        
        elif self.lifetime == ServiceLifetime.SCOPED:
            # Для scoped используем instance как singleton в рамках scope
            if self._instance is None:
                self._instance = self._create_instance(container)
            return self._instance
        
        raise ValueError(f"Unknown lifetime: {self.lifetime}")
    
    def _create_instance(self, container: 'DependencyContainer') -> T:
        """Создать экземпляр службы."""
        if self._implementation is not None:
            return self._implementation
        
        if self._factory is not None:
            return self._factory()
        
        raise ValueError(f"No implementation or factory for {self.interface}")
    
    def reset_instance(self):
        """Сбросить экземпляр (для singleton)."""
        self._instance = None


class DependencyContainer:
    """
    DI контейнер для управления зависимостями.
    
    FEATURES:
    - Регистрация по интерфейсам (Protocol)
    - Три времени жизни: singleton, transient, scoped
    - Автоматическое разрешение зависимостей
    - Поддержка вложенных контейнеров (scoped)
    """
    
    def __init__(self, parent: Optional['DependencyContainer'] = None):
        """
        Инициализация контейнера.
        
        ARGS:
        - parent: Родительский контейнер (для scoped контейнеров)
        """
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._parent = parent
        self._event_bus_logger = None
        self._is_disposed = False
    
    def set_logger(self, logger: EventBusLogger):
        """Установить логгер для отладки."""
        self._event_bus_logger = logger
    
    async def _log_debug(self, message: str, *args):
        """Отладочное сообщение."""
        if self._event_bus_logger:
            await self._event_bus_logger.debug(message, *args)
    
    # ========================================================================
    # РЕГИСТРАЦИЯ СЛУЖБ
    # ========================================================================
    
    def register_singleton(
        self,
        interface: Type[T],
        implementation: T
    ) -> 'DependencyContainer':
        """
        Зарегистрировать singleton реализацию интерфейса.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        - implementation: Экземпляр реализации
        
        RETURNS:
        - Self для цепочки вызовов
        
        USAGE:
        ```python
        container.register_singleton(DatabaseInterface, postgresql_provider)
        ```
        """
        if self._is_disposed:
            raise RuntimeError("Container is disposed")
        
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON
        )
        self._services[interface] = descriptor
        
        if self._event_bus_logger:
            import asyncio
            asyncio.create_task(
                self._log_debug(
                    "Зарегистрирован singleton: %s → %s",
                    interface.__name__,
                    type(implementation).__name__
                )
            )
        
        return self
    
    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    ) -> 'DependencyContainer':
        """
        Зарегистрировать фабрику для создания экземпляров.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        - factory: Фабрика для создания экземпляров
        - lifetime: Время жизни службы
        
        RETURNS:
        - Self для цепочки вызовов
        
        USAGE:
        ```python
        container.register_factory(
            DatabaseInterface,
            lambda: PostgreSQLProvider(config),
            ServiceLifetime.SINGLETON
        )
        ```
        """
        if self._is_disposed:
            raise RuntimeError("Container is disposed")
        
        descriptor = ServiceDescriptor(
            interface=interface,
            factory=factory,
            lifetime=lifetime
        )
        self._services[interface] = descriptor
        
        if self._event_bus_logger:
            import asyncio
            asyncio.create_task(
                self._log_debug(
                    "Зарегистрирована фабрика: %s (lifetime=%s)",
                    interface.__name__,
                    lifetime.value
                )
            )
        
        return self
    
    def register_instance(
        self,
        interface: Type[T],
        instance: T
    ) -> 'DependencyContainer':
        """
        Зарегистрировать экземпляр интерфейса.
        
        Алиас для register_singleton.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        - instance: Экземпляр реализации
        
        RETURNS:
        - Self для цепочки вызовов
        """
        return self.register_singleton(interface, instance)
    
    # ========================================================================
    # РАЗРЕШЕНИЕ ЗАВИСИМОСТЕЙ
    # ========================================================================
    
    def resolve(self, interface: Type[T]) -> T:
        """
        Получить реализацию интерфейса.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        
        RETURNS:
        - Экземпляр реализации
        
        RAISES:
        - ValueError: Если интерфейс не зарегистрирован
        
        USAGE:
        ```python
        db = container.resolve(DatabaseInterface)
        llm = container.resolve(LLMInterface)
        ```
        """
        if self._is_disposed:
            raise RuntimeError("Container is disposed")
        
        # Проверяем текущий контейнер
        if interface in self._services:
            descriptor = self._services[interface]
            return descriptor.get_instance(self)
        
        # Проверяем родительский контейнер
        if self._parent is not None:
            return self._parent.resolve(interface)
        
        # Не найдено
        raise ValueError(
            f"No registration for interface: {interface.__name__}. "
            f"Available: {list(self._services.keys())}"
        )
    
    def resolve_optional(self, interface: Type[T]) -> Optional[T]:
        """
        Получить реализацию интерфейса или None.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        
        RETURNS:
        - Экземпляр реализации или None
        """
        try:
            return self.resolve(interface)
        except ValueError:
            return None
    
    def resolve_all(self, interface: Type[T]) -> List[T]:
        """
        Получить все реализации интерфейса.
        
        ARGS:
        - interface: Тип интерфейса (Protocol)
        
        RETURNS:
        - Список экземпляров
        """
        results = []
        
        # Собираем из родительского контейнера
        if self._parent is not None:
            results.extend(self._parent.resolve_all(interface))
        
        # Добавляем из текущего
        for descriptor in self._services.values():
            if descriptor.interface == interface:
                results.append(descriptor.get_instance(self))
        
        return results
    
    # ========================================================================
    # SCOPED КОНТЕЙНЕРЫ
    # ========================================================================
    
    def create_scope(self) -> 'DependencyContainer':
        """
        Создать scoped контейнер.
        
        Scoped контейнер наследует регистрации от родителя,
        но может иметь свои собственные singleton в рамках scope.
        
        RETURNS:
        - Новый scoped контейнер
        
        USAGE:
        ```python
        with container.create_scope() as scope:
            db = scope.resolve(DatabaseInterface)
            # db будет тем же в рамках scope
        ```
        """
        return DependencyContainer(parent=self)
    
    # ========================================================================
    # УПРАВЛЕНИЕ ЖИЗНЕННЫМ ЦИКЛОМ
    # ========================================================================
    
    def dispose(self):
        """
        Освободить ресурсы контейнера.
        
        Сбрасывает все singleton экземпляры.
        """
        if self._is_disposed:
            return
        
        for descriptor in self._services.values():
            descriptor.reset_instance()
        
        self._services.clear()
        self._is_disposed = True
        
        if self._event_bus_logger:
            import asyncio
            asyncio.create_task(
                self._log_debug("Контейнер зависимостей освобождён")
            )
    
    def __enter__(self) -> 'DependencyContainer':
        """Вход в контекст."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста."""
        self.dispose()
    
    # ========================================================================
    # ДИАГНОСТИКА
    # ========================================================================
    
    def get_registered_interfaces(self) -> List[Type]:
        """Получить список зарегистрированных интерфейсов."""
        return list(self._services.keys())
    
    def is_registered(self, interface: Type) -> bool:
        """Проверить, зарегистрирован ли интерфейс."""
        return interface in self._services
    
    def get_service_info(self, interface: Type) -> Optional[Dict[str, Any]]:
        """Получить информацию о службе."""
        if interface not in self._services:
            return None
        
        descriptor = self._services[interface]
        return {
            "interface": interface.__name__,
            "lifetime": descriptor.lifetime.value,
            "has_instance": descriptor._instance is not None,
            "has_factory": descriptor._factory is not None
        }
    
    def get_all_service_info(self) -> List[Dict[str, Any]]:
        """Получить информацию обо всех службах."""
        return [
            self.get_service_info(interface)
            for interface in self._services.keys()
        ]
