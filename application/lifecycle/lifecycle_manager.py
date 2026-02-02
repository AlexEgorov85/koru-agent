"""
Менеджер жизненного цикла - компонент для управления жизненным циклом системы и ее компонентов.
Располагается в application слое в соответствии с архитектурными принципами.
"""
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod
import asyncio
from enum import Enum


class ComponentState(Enum):
    """
    Перечисление состояний компонента.
    """
    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"


class ILifecycleManager(ABC):
    """
    Интерфейс для менеджера жизненного цикла.
    """
    
    @abstractmethod
    def register_component(self, component_name: str, component: Any):
        """
        Зарегистрировать компонент для управления жизненным циклом
        
        Args:
            component_name: Имя компонента
            component: Объект компонента
        """
        pass
    
    @abstractmethod
    async def initialize_component(self, component_name: str):
        """
        Инициализировать компонент
        
        Args:
            component_name: Имя компонента
        """
        pass
    
    @abstractmethod
    async def start_component(self, component_name: str):
        """
        Запустить компонент
        
        Args:
            component_name: Имя компонента
        """
        pass
    
    @abstractmethod
    async def stop_component(self, component_name: str):
        """
        Остановить компонент
        
        Args:
            component_name: Имя компонента
        """
        pass
    
    @abstractmethod
    async def shutdown_component(self, component_name: str):
        """
        Завершить работу компонента
        
        Args:
            component_name: Имя компонента
        """
        pass
    
    @abstractmethod
    async def initialize_all(self):
        """
        Инициализировать все зарегистрированные компоненты
        """
        pass
    
    @abstractmethod
    async def start_all(self):
        """
        Запустить все зарегистрированные компоненты
        """
        pass
    
    @abstractmethod
    async def stop_all(self):
        """
        Остановить все зарегистрированные компоненты
        """
        pass
    
    @abstractmethod
    async def shutdown_all(self):
        """
        Завершить работу всех зарегистрированных компонентов
        """
        pass


class LifecycleManager(ILifecycleManager):
    """
    Реализация менеджера жизненного цикла.
    """
    
    def __init__(self):
        """
        Инициализация менеджера жизненного цикла.
        """
        self._components: Dict[str, Any] = {}
        self._states: Dict[str, ComponentState] = {}
        self._initialization_order: List[str] = []
    
    def register_component(self, component_name: str, component: Any):
        """
        Зарегистрировать компонент для управления жизненным циклом
        
        Args:
            component_name: Имя компонента
            component: Объект компонента
        """
        self._components[component_name] = component
        self._states[component_name] = ComponentState.CREATED
        self._initialization_order.append(component_name)
    
    async def initialize_component(self, component_name: str):
        """
        Инициализировать компонент
        
        Args:
            component_name: Имя компонента
        """
        if component_name not in self._components:
            raise ValueError(f"Component {component_name} is not registered")
        
        component = self._components[component_name]
        
        # Проверяем текущее состояние
        if self._states[component_name] != ComponentState.CREATED:
            raise ValueError(f"Component {component_name} is not in CREATED state")
        
        # Вызываем метод инициализации, если он существует
        if hasattr(component, 'initialize'):
            if asyncio.iscoroutinefunction(component.initialize):
                await component.initialize()
            else:
                component.initialize()
        
        self._states[component_name] = ComponentState.INITIALIZED
    
    async def start_component(self, component_name: str):
        """
        Запустить компонент
        
        Args:
            component_name: Имя компонента
        """
        if component_name not in self._components:
            raise ValueError(f"Component {component_name} is not registered")
        
        component = self._components[component_name]
        
        # Проверяем текущее состояние
        if self._states[component_name] != ComponentState.INITIALIZED:
            raise ValueError(f"Component {component_name} is not in INITIALIZED state")
        
        # Вызываем метод запуска, если он существует
        if hasattr(component, 'start'):
            if asyncio.iscoroutinefunction(component.start):
                await component.start()
            else:
                component.start()
        
        self._states[component_name] = ComponentState.STARTED
    
    async def stop_component(self, component_name: str):
        """
        Остановить компонент
        
        Args:
            component_name: Имя компонента
        """
        if component_name not in self._components:
            raise ValueError(f"Component {component_name} is not registered")
        
        component = self._components[component_name]
        
        # Проверяем текущее состояние
        if self._states[component_name] != ComponentState.STARTED:
            raise ValueError(f"Component {component_name} is not in STARTED state")
        
        # Вызываем метод остановки, если он существует
        if hasattr(component, 'stop'):
            if asyncio.iscoroutinefunction(component.stop):
                await component.stop()
            else:
                component.stop()
        
        self._states[component_name] = ComponentState.STOPPED
    
    async def shutdown_component(self, component_name: str):
        """
        Завершить работу компонента
        
        Args:
            component_name: Имя компонента
        """
        if component_name not in self._components:
            raise ValueError(f"Component {component_name} is not registered")
        
        component = self._components[component_name]
        
        # Проверяем текущее состояние
        if self._states[component_name] not in [ComponentState.STOPPED, ComponentState.INITIALIZED]:
            raise ValueError(f"Component {component_name} is not in STOPPED or INITIALIZED state")
        
        # Вызываем метод завершения работы, если он существует
        if hasattr(component, 'shutdown'):
            if asyncio.iscoroutinefunction(component.shutdown):
                await component.shutdown()
            else:
                component.shutdown()
        
        self._states[component_name] = ComponentState.SHUTDOWN
    
    async def initialize_all(self):
        """
        Инициализировать все зарегистрированные компоненты
        """
        for component_name in self._initialization_order:
            if self._states[component_name] == ComponentState.CREATED:
                await self.initialize_component(component_name)
    
    async def start_all(self):
        """
        Запустить все зарегистрированные компоненты
        """
        for component_name in self._initialization_order:
            if self._states[component_name] == ComponentState.INITIALIZED:
                await self.start_component(component_name)
    
    async def stop_all(self):
        """
        Остановить все зарегистрированные компоненты
        """
        # Останавливаем в обратном порядке
        for component_name in reversed(self._initialization_order):
            if self._states[component_name] == ComponentState.STARTED:
                await self.stop_component(component_name)
    
    async def shutdown_all(self):
        """
        Завершить работу всех зарегистрированных компонентов
        """
        # Завершаем работу в обратном порядке
        for component_name in reversed(self._initialization_order):
            if self._states[component_name] in [ComponentState.STOPPED, ComponentState.INITIALIZED]:
                await self.shutdown_component(component_name)