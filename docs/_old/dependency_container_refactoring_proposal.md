# Предложение по рефакторингу DependencyContainer

## Текущая проблема

Файл `core/dependency_container.py` представляет собой контейнер внедрения зависимостей (DI-контейнер), который в текущей реализации может нарушать архитектурные границы, позволяя зависимостям из разных слоев свободно переплетаться. 

Основные проблемы:
1. Глобальное состояние контейнера может привести к трудноотслеживаемым зависимостям
2. Контейнер может регистрировать зависимости из разных слоев без должного контроля над архитектурными границами
3. Нарушение принципа инверсии зависимостей (DIP) при неправильном использовании

## Предлагаемое разбиение и улучшения

### 1. Базовый интерфейс (остается в текущем месте)

Файл: `core/dependency_container/interfaces.py`

```python
from typing import Dict, Type, Any, Optional, Callable
from abc import ABC, abstractmethod

class IDependencyContainer(ABC):
    """Интерфейс для DI-контейнера"""
    
    @abstractmethod
    def register(self, interface: Type, implementation: Type, singleton: bool = True):
        """Регистрация зависимости"""
        pass
    
    @abstractmethod
    def register_instance(self, interface: Type, instance: Any):
        """Регистрация конкретного экземпляра"""
        pass
    
    @abstractmethod
    def resolve(self, interface: Type) -> Any:
        """Получение зависимости"""
        pass
    
    @abstractmethod
    def resolve_optional(self, interface: Type) -> Optional[Any]:
        """Получение зависимости (опционально)"""
        pass
```

### 2. Основной контейнер (переходит в Infrastructure слой)

Файл: `core/infrastructure/dependency_container/container.py`

```python
from typing import Dict, Type, Any, Optional, Callable
from core.dependency_container.interfaces import IDependencyContainer

class DependencyContainer(IDependencyContainer):
    """Реализация DI-контейнера с поддержкой архитектурных границ"""
    
    def __init__(self, enforce_architecture_boundaries: bool = False):
        self._registrations: Dict[Type, Type] = {}
        self._instances: Dict[Type, Any] = {}
        self._singletons: Dict[Type, bool] = {}
        self._factory_functions: Dict[Type, Callable] = {}
        self._architecture_boundaries_enabled = enforce_architecture_boundaries
        self._layer_hierarchy = {
            'domain': 0,
            'application': 1,
            'infrastructure': 2,
            'interfaces': 3
        }
        self._registered_layers: Dict[Type, str] = {}
    
    def register(self, interface: Type, implementation: Type, singleton: bool = True, layer: str = None):
        """
        Регистрация зависимости с возможностью указания слоя.
        
        Args:
            interface: Интерфейс или абстрактный класс
            implementation: Конкретная реализация
            singleton: Является ли синглтоном
            layer: Архитектурный слой (domain, application, infrastructure, interfaces)
        """
        if self._architecture_boundaries_enabled and layer:
            self._registered_layers[interface] = layer
        
        self._registrations[interface] = implementation
        self._singletons[interface] = singleton
        
        if singleton and interface in self._instances:
            del self._instances[interface]  # Удаляем старый экземпляр при повторной регистрации
    
    def register_factory(self, interface: Type, factory_func: Callable, singleton: bool = True, layer: str = None):
        """
        Регистрация фабричной функции.
        
        Args:
            interface: Интерфейс или абстрактный класс
            factory_func: Фабричная функция для создания экземпляра
            singleton: Является ли синглтоном
            layer: Архитектурный слой
        """
        if self._architecture_boundaries_enabled and layer:
            self._registered_layers[interface] = layer
            
        self._factory_functions[interface] = factory_func
        self._singletons[interface] = singleton
        
        if singleton and interface in self._instances:
            del self._instances[interface]  # Удаляем старый экземпляр при повторной регистрации
    
    def register_instance(self, interface: Type, instance: Any, layer: str = None):
        """
        Регистрация конкретного экземпляра.
        
        Args:
            interface: Интерфейс или абстрактный класс
            instance: Конкретный экземпляр
            layer: Архитектурный слой
        """
        if self._architecture_boundaries_enabled and layer:
            self._registered_layers[interface] = layer
            
        self._instances[interface] = instance
    
    def resolve(self, interface: Type) -> Any:
        """
        Получение зависимости с проверкой архитектурных границ при включенном режиме.
        
        Args:
            interface: Интерфейс или абстрактный класс для получения
            
        Returns:
            Экземпляр реализации
            
        Raises:
            KeyError: Если зависимость не зарегистрирована
            ValueError: Если происходит нарушение архитектурных границ
        """
        # Проверяем архитектурные границы, если включено
        if self._architecture_boundaries_enabled:
            caller_layer = self._get_caller_layer()
            dependency_layer = self._registered_layers.get(interface)
            if caller_layer and dependency_layer and self._is_invalid_dependency(caller_layer, dependency_layer):
                raise ValueError(f"Нарушение архитектурной границы: {caller_layer} не может зависеть от {dependency_layer}")
        
        # Сначала проверяем, есть ли уже созданный экземпляр для синглтонов
        if interface in self._instances:
            return self._instances[interface]
        
        # Проверяем, есть ли регистрация
        if interface not in self._registrations and interface not in self._factory_functions:
            raise KeyError(f"Зависимость {interface.__name__} не зарегистрирована")
        
        # Создаем экземпляр
        if interface in self._factory_functions:
            instance = self._factory_functions[interface]()
        else:
            implementation = self._registrations[interface]
            # Рекурсивно разрешаем зависимости конструктора
            instance = self._create_instance(implementation)
        
        # Сохраняем экземпляр для синглтонов
        if self._singletons.get(interface, True):
            self._instances[interface] = instance
        
        return instance
    
    def resolve_optional(self, interface: Type) -> Optional[Any]:
        """
        Получение зависимости (опционально) с проверкой архитектурных границ.
        
        Args:
            interface: Интерфейс или абстрактный класс для получения
            
        Returns:
            Экземпляр реализации или None, если не зарегистрирован
        """
        try:
            return self.resolve(interface)
        except KeyError:
            return None

    def _create_instance(self, cls: Type) -> Any:
        """
        Создание экземпляра класса с разрешением зависимостей конструктора.
        
        Args:
            cls: Класс для создания экземпляра
            
        Returns:
            Экземпляр класса
        """
        import inspect
        
        # Получаем сигнатуру конструктора
        init_signature = inspect.signature(cls.__init__)
        parameters = init_signature.parameters
        
        # Подготовим аргументы для конструктора
        constructor_args = {}
        for param_name, param in parameters.items():
            if param_name == 'self':
                continue
                
            # Проверяем аннотацию параметра
            if param.annotation != inspect.Parameter.empty:
                try:
                    resolved_dependency = self.resolve(param.annotation)
                    constructor_args[param_name] = resolved_dependency
                except KeyError:
                    # Если зависимость не найдена, проверяем, есть ли значение по умолчанию
                    if param.default != inspect.Parameter.empty:
                        constructor_args[param_name] = param.default
                    else:
                        raise ValueError(f"Не удалось разрешить зависимость {param.annotation.__name__} для параметра {param_name}")
            elif param.default != inspect.Parameter.empty:
                # Если нет аннотации, но есть значение по умолчанию, используем его
                constructor_args[param_name] = param.default
            else:
                # Если нет аннотации и нет значения по умолчанию, пропускаем (может быть примитив)
                continue
        
        # Создаем экземпляр
        return cls(**constructor_args)
    
    def _get_caller_layer(self) -> Optional[str]:
        """
        Определяет архитектурный слой вызывающего кода (упрощенная реализация).
        """
        import inspect
        frame = inspect.currentframe()
        try:
            # Идем по стеку вызовов, чтобы определить слой
            for _ in range(5):  # Проверяем несколько уровней стека
                frame = frame.f_back
                if frame is None:
                    break
                filename = frame.f_code.co_filename
                # Определяем слой по пути к файлу
                if '/domain/' in filename or '\\domain\\' in filename:
                    return 'domain'
                elif '/application/' in filename or '\\application\\' in filename:
                    return 'application'
                elif '/infrastructure/' in filename or '\\infrastructure\\' in filename:
                    return 'infrastructure'
                elif '/interfaces/' in filename or '\\interfaces\\' in filename:
                    return 'interfaces'
        finally:
            del frame
        return None

    def _is_invalid_dependency(self, caller_layer: str, dependency_layer: str) -> bool:
        """
        Проверяет, является ли зависимость недопустимой с точки зрения архитектурных границ.
        """
        caller_level = self._layer_hierarchy.get(caller_layer, -1)
        dependency_level = self._layer_hierarchy.get(dependency_layer, -1)
        # Вызывающий слой не может зависеть от более высокого уровня
        return dependency_level < caller_level
```

### 3. Менеджер зависимостей приложения (Application слой)

Файл: `core/application/dependency_management/container_manager.py`

```python
from typing import Type, Any
from core.dependency_container.interfaces import IDependencyContainer

class ContainerManager:
    """Управление контейнером зависимостей на уровне приложения"""
    
    def __init__(self, container: IDependencyContainer):
        self.container = container
        self._configured = False
    
    def configure_defaults(self):
        """Конфигурирует стандартные зависимости для приложения"""
        if self._configured:
            return
            
        # Регистрация стандартных зависимостей приложения
        # Например, сервисы приложения, фабрики и т.д.
        # Здесь важно следовать архитектурным границам
        
        self._configured = True
    
    def register_application_service(self, interface: Type, implementation: Type, singleton: bool = True):
        """Регистрация сервиса уровня приложения"""
        self.container.register(interface, implementation, singleton, layer='application')
    
    def register_infrastructure_service(self, interface: Type, implementation: Type, singleton: bool = True):
        """Регистрация сервиса уровня инфраструктуры"""
        self.container.register(interface, implementation, singleton, layer='infrastructure')
    
    def register_domain_service(self, interface: Type, implementation: Type, singleton: bool = True):
        """Регистрация сервиса уровня домена"""
        self.container.register(interface, implementation, singleton, layer='domain')
    
    def resolve(self, interface: Type) -> Any:
        """Разрешение зависимости через контейнер"""
        return self.container.resolve(interface)
```

### 4. Фабрика контейнеров (Infrastructure слой)

Файл: `core/infrastructure/dependency_container/container_factory.py`

```python
from core.infrastructure.dependency_container.container import DependencyContainer
from core.application.dependency_management.container_manager import ContainerManager

class ContainerFactory:
    """Фабрика для создания и настройки контейнеров зависимостей"""
    
    @staticmethod
    def create_default_container(enforce_architecture_boundaries: bool = True) -> DependencyContainer:
        """Создает контейнер с архитектурными ограничениями"""
        return DependencyContainer(enforce_architecture_boundaries=enforce_architecture_boundaries)
    
    @staticmethod
    def create_container_with_defaults(enforce_architecture_boundaries: bool = True) -> tuple[DependencyContainer, ContainerManager]:
        """Создает контейнер с менеджером и настраивает стандартные зависимости"""
        container = ContainerFactory.create_default_container(enforce_architecture_boundaries)
        manager = ContainerManager(container)
        manager.configure_defaults()
        return container, manager
```

### 5. Утилиты для глобального контейнера (Infrastructure слой)

Файл: `core/infrastructure/dependency_container/global_container.py`

```python
from typing import Optional
from core.infrastructure.dependency_container.container import DependencyContainer

# Глобальный контейнер зависимостей
_global_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Получение глобального контейнера зависимостей"""
    global _global_container
    if _global_container is None:
        from core.infrastructure.dependency_container.container_factory import ContainerFactory
        _global_container = ContainerFactory.create_default_container(enforce_architecture_boundaries=True)
    return _global_container


def set_container(container: DependencyContainer):
    """Установка глобального контейнера зависимостей"""
    global _global_container
    _global_container = container  # type: ignore


def register_dependency(interface: type, implementation: type, singleton: bool = True):
    """Регистрация зависимости в глобальном контейнере"""
    container = get_container()
    container.register(interface, implementation, singleton)


def resolve_dependency(interface: type) -> any:
    """Получение зависимости из глобального контейнера"""
    container = get_container()
    return container.resolve(interface)
```

## Преимущества предлагаемого подхода

1. **Архитектурные границы**: Контейнер может проверять зависимости между слоями и предотвращать нарушения архитектурных границ
2. **Расширенная функциональность**: Менеджер контейнера предоставляет удобные методы для регистрации сервисов по слоям
3. **Лучшая тестируемость**: Возможность легко создавать изолированные контейнеры для тестирования
4. **Явное управление зависимостями**: Регистрация зависимостей теперь требует указания слоя, что делает архитектуру более прозрачной
5. **Соблюдение принципа инверсии зависимостей**: Модули высокого уровня не зависят от модулей низкого уровня через реализации

## План миграции

1. Создать новые файлы с улучшенной архитектурой
2. Обновить все импорты в проекте, чтобы использовать новые пути
3. Постепенно перенести функциональность из старого DependencyContainer в новые компоненты
4. После проверки работоспособности обновить старый файл или заменить его новой реализацией
5. Обновить тесты для соответствия новой архитектуре

## Зависимости

- Infrastructure слой: `core/infrastructure/dependency_container/container.py`, `core/infrastructure/dependency_container/container_factory.py`, `core/infrastructure/dependency_container/global_container.py`
- Application слой: `core/application/dependency_management/container_manager.py`
- Interface слой: `core/dependency_container/interfaces.py`

Таким образом, мы достигаем более строгой архитектуры, соответствующей принципам SOLID и Clean Architecture, при этом сохраняя всю функциональность оригинального контейнера зависимостей с дополнительными возможностями проверки архитектурных границ.