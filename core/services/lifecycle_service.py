"""
Сервис жизненного цикла - синглтон для управления ресурсами и компонентами.

АРХИТЕКТУРА:
- Единый LifecycleManager для инфраструктуры и компонентов
- Ленивая инициализация через get_instance()
- Автоматическое управление зависимостями между ресурсами

USAGE:
```python
# Получение экземпляра
lifecycle_service = LifecycleService.get_instance(event_bus)

# Регистрация ресурсов
await lifecycle_service.register_infrastructure(name, resource, type)
await lifecycle_service.register_component(name, component, type)

# Инициализация всех
await lifecycle_service.initialize_all()

# Завершение
await lifecycle_service.shutdown_all()
```
"""
from typing import Any, Optional, Dict, List
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure_context.lifecycle_manager import LifecycleManager


class LifecycleService:
    """
    Сервис жизненного цикла - синглтон.
    
    Предоставляет единую точку доступа к LifecycleManager для:
    - Инфраструктурных ресурсов (провайдеры, хранилища)
    - Компонентов приложения (skills, tools, services, behaviors)
    """
    _instance: Optional['LifecycleService'] = None
    _manager: Optional[LifecycleManager] = None
    _event_bus: Optional[UnifiedEventBus] = None

    def __init__(self, event_bus: UnifiedEventBus):
        """
        Инициализация (только через get_instance).
        
        ARGS:
        - event_bus: шина событий для логирования
        """
        if LifecycleService._instance is not None:
            raise RuntimeError("Use LifecycleService.get_instance()")
        
        self._manager = LifecycleManager(event_bus)
        self._event_bus = event_bus

    @classmethod
    def get_instance(cls, event_bus: Optional[UnifiedEventBus] = None) -> 'LifecycleService':
        """
        Получение экземпляра сервиса (синглтон).
        
        ARGS:
        - event_bus: шина событий (required при первом вызове)
        
        RETURNS:
        - LifecycleService: экземпляр сервиса
        """
        if cls._instance is None:
            if event_bus is None:
                raise ValueError("event_bus required при первом вызове LifecycleService.get_instance()")
            cls._instance = cls(event_bus)
        
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Сброс экземпляра (для тестов).
        """
        cls._instance = None
        cls._manager = None
        cls._event_bus = None

    @property
    def manager(self) -> LifecycleManager:
        """Получение LifecycleManager."""
        if self._manager is None:
            raise RuntimeError("LifecycleService не инициализирована")
        return self._manager

    @property
    def resources_count(self) -> int:
        return self._manager.resources_count if self._manager else 0

    @property
    def is_initialized(self) -> bool:
        return self._manager.is_initialized if self._manager else False

    @property
    def is_ready(self) -> bool:
        return self._manager.is_ready if self._manager else False

    async def register_infrastructure(
        self,
        name: str,
        resource: Any,
        resource_type: Any,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Регистрация инфраструктурного ресурса."""
        await self._manager.register_infrastructure(name, resource, resource_type, dependencies, metadata)

    async def register_component(
        self,
        name: str,
        component: Any,
        component_type: Optional[Any] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Регистрация компонента приложения."""
        await self._manager.register_component(name, component, component_type, dependencies, metadata)

    async def register_resource(
        self,
        name: str,
        resource: Any,
        resource_type: Any,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Универсальная регистрация ресурса."""
        await self._manager.register_resource(name, resource, resource_type, dependencies, metadata)

    async def initialize_all(self) -> Dict[str, bool]:
        """Инициализация всех зарегистрированных ресурсов."""
        return await self._manager.initialize_all()

    async def shutdown_all(self) -> Dict[str, bool]:
        """Завершение всех ресурсов."""
        return await self._manager.shutdown_all()

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Проверка здоровья всех ресурсов."""
        return await self._manager.health_check_all()

    def get_resource(self, name: str) -> Optional[Any]:
        """Получение ресурса по имени."""
        return self._manager.get_resource(name) if self._manager else None

    def get_resources_by_type(self, resource_type: Any) -> List[Any]:
        """Получение ресурсов по типу."""
        return self._manager.get_resources_by_type(resource_type) if self._manager else []

    def get_all_info(self) -> Dict[str, Dict[str, Any]]:
        """Получение информации обо всех ресурсах."""
        return self._manager.get_all_info() if self._manager else {}

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики."""
        return self._manager.get_stats() if self._manager else {}
