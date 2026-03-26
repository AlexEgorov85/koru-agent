"""
Менеджер жизненного цикла инфраструктурных ресурсов.

АРХИТЕКТУРА:
- Единый менеджер для всех инфраструктурных ресурсов
- Поддержка зависимостей между ресурсами (топологическая сортировка)
- Типизация ресурсов и отслеживание состояния
- Проверка здоровья (health check)
- Обратная совместимость с register_initializer/register_cleanup

FEATURES:
- Регистрация ресурсов с зависимостями
- Автоматический порядок инициализации на основе графа зависимостей
- Корректный shutdown в обратном порядке
- Health check всех ресурсов
- Статистика и мониторинг состояния
- Интеграция с Event Bus для наблюдаемости
"""
from typing import List, Callable, Awaitable, Any, Optional, Dict, Protocol
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from core.infrastructure.logging import EventBusLogger
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.agent.components.lifecycle import ComponentState
from core.models.enums.common_enums import ResourceType


class ManagedResource(Protocol):
    """
    Протокол для ресурсов, управляемых LifecycleManager.
    
    Все ресурсы должны реализовать эти методы для полноценного управления.
    Если методы отсутствуют, LifecycleManager использует заглушки.
    """

    async def initialize(self) -> bool:
        """Асинхронная инициализация ресурса."""
        ...

    async def shutdown(self) -> None:
        """Корректное завершение работы ресурса."""
        ...

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья. Возвращает статус и метрики."""
        ...

    def get_info(self) -> Dict[str, Any]:
        """Базовая информация (имя, тип, состояние)."""
        ...


@dataclass
class ResourceRecord:
    """
    Информация о зарегистрированном ресурсе.
    
    ATTRIBUTES:
    - name: уникальное имя ресурса
    - resource: экземпляр ресурса (должен соответствовать ManagedResource)
    - resource_type: тип ресурса
    - dependencies: список имён ресурсов, от которых зависит данный
    - status: текущий статус
    - metadata: дополнительные метаданные
    - init_error: сообщение об ошибке инициализации (если была)
    - registered_at: время регистрации
    - initialized_at: время успешной инициализации
    """
    name: str
    resource: Any
    resource_type: ResourceType
    dependencies: List[str] = field(default_factory=list)
    status: ComponentState = ComponentState.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    init_error: Optional[str] = None
    registered_at: datetime = field(default_factory=datetime.now)
    initialized_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации."""
        return {
            "name": self.name,
            "resource_type": self.resource_type.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "init_error": self.init_error,
            "registered_at": self.registered_at.isoformat(),
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
        }


class LifecycleManager:
    """
    Менеджер жизненного цикла инфраструктурных ресурсов.
    
    Управляет инициализацией и завершением работы ресурсов с поддержкой:
    - Зависимостей между ресурсами (топологическая сортировка)
    - Типизации ресурсов
    - Проверки здоровья
    - Отслеживания состояния
    
    USAGE:
    ```python
    # Создание менеджера
    lifecycle_manager = LifecycleManager(event_bus)
    
    # Регистрация ресурса с зависимостями
    await lifecycle_manager.register_resource(
        name="llm_provider",
        resource=provider,
        resource_type=ResourceType.LLM,
        dependencies=["db_provider"],  # LLM зависит от БД
        metadata={"is_default": True}
    )
    
    # Инициализация всех ресурсов (с учётом зависимостей)
    await lifecycle_manager.initialize_all()
    
    # Проверка здоровья
    health_results = await lifecycle_manager.health_check_all()
    
    # Завершение работы (в обратном порядке)
    await lifecycle_manager.shutdown_all()
    ```
    """

    def __init__(self, event_bus: Optional[UnifiedEventBus] = None):
        self._resources: Dict[str, ResourceRecord] = {}
        self._initialized = False
        self._shutdown_in_progress = False
        self.event_bus: Optional[UnifiedEventBus] = event_bus
        self.event_bus_logger: Optional[EventBusLogger] = None
        self._lock = asyncio.Lock()
        
        if event_bus:
            self.event_bus_logger = EventBusLogger(
                event_bus, 
                session_id="system", 
                agent_id="system", 
                component="LifecycleManager"
            )

    # ==================== РЕГИСТРАЦИЯ РЕСУРСОВ ====================

    async def register_resource(
        self,
        name: str,
        resource: Any,
        resource_type: ResourceType,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Регистрация ресурса для управления.
        
        ARGS:
        - name: уникальное имя ресурса
        - resource: экземпляр ресурса
        - resource_type: тип ресурса
        - dependencies: список имён ресурсов, от которых зависит данный
        - metadata: дополнительные метаданные
        
        RAISES:
        - ValueError: если ресурс с таким именем уже зарегистрирован
        """
        async with self._lock:
            if name in self._resources:
                raise ValueError(f"Resource '{name}' already registered")
            
            record = ResourceRecord(
                name=name,
                resource=resource,
                resource_type=resource_type,
                dependencies=dependencies or [],
                metadata=metadata or {}
            )
            self._resources[name] = record
            
            await self._publish_event("resource_registered", {
                "name": name, 
                "type": resource_type.value
            })
            
            if self.event_bus_logger:
                await self.event_bus_logger.debug(
                    "Зарегистрирован ресурс '%s' типа %s", 
                    name, resource_type.value
                )

    # ==================== УДОБНЫЕ МЕТОДЫ РЕГИСТРАЦИИ ====================

    async def register_infrastructure(
        self,
        name: str,
        resource: Any,
        resource_type: ResourceType,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Регистрация инфраструктурного ресурса (провайдеры, хранилища).
        
        Псевдоним для register_resource с типом инфраструктуры.
        """
        await self.register_resource(name, resource, resource_type, dependencies, metadata)

    async def register_component(
        self,
        name: str,
        component: Any,
        component_type: Optional[ResourceType] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Регистрация компонента приложения (skills, tools, services, behaviors).
        
        ARGS:
        - name: уникальное имя компонента
        - component: экземпляр компонента (BaseComponent)
        - component_type: тип компонента (SKILL, TOOL, SERVICE, BEHAVIOR)
        - dependencies: список имён ресурсов, от которых зависит компонент
        - metadata: дополнительные метаданные
        
        NOTE: Если component_type не указан, определяется автоматически
        """
        if component_type is None:
            component_type = self._detect_component_type(component)
        
        await self.register_resource(name, component, component_type, dependencies, metadata)
    
    def _detect_component_type(self, component: Any) -> ResourceType:
        """Определение типа компонента по классу."""
        class_name = component.__class__.__name__
        if "Skill" in class_name:
            return ResourceType.SKILL
        elif "Tool" in class_name:
            return ResourceType.TOOL
        elif "Service" in class_name:
            return ResourceType.SERVICE
        elif "Behavior" in class_name or "BehaviorPattern" in class_name:
            return ResourceType.BEHAVIOR
        return ResourceType.OTHER

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    async def initialize_all(self) -> Dict[str, bool]:
        """
        Инициализация всех зарегистрированных ресурсов с учётом зависимостей.
        
        Порядок инициализации определяется топологической сортировкой графа зависимостей.
        
        RETURNS:
        - Dict[str, bool]: результаты инициализации по каждому ресурсу
        
        RAISES:
        - RuntimeError: если обнаружена циклическая зависимость
        """
        async with self._lock:
            if self._initialized:
                if self.event_bus_logger:
                    await self.event_bus_logger.warning("LifecycleManager уже инициализирован")
                return {name: True for name in self._resources}

            if self.event_bus_logger is None and self.event_bus:
                self.event_bus_logger = EventBusLogger(
                    self.event_bus, 
                    session_id="system", 
                    agent_id="system", 
                    component="LifecycleManager"
                )

            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    "Начало инициализации %d инфраструктурных ресурсов",
                    len(self._resources)
                )

            # Построение графа зависимостей
            graph = {name: set(record.dependencies) for name, record in self._resources.items()}
            
            # Топологическая сортировка
            order = self._topological_sort(graph)
            if order is None:
                raise RuntimeError("Circular dependency detected among resources")

            results = {}
            for name in order:
                record = self._resources[name]
                
                # Проверка зависимостей
                failed_deps = [
                    dep for dep in record.dependencies 
                    if dep in results and not results[dep]
                ]
                if failed_deps:
                    record.status = ComponentState.FAILED
                    record.init_error = f"Failed dependencies: {failed_deps}"
                    results[name] = False
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            "Ресурс '%s' не инициализирован:_failed зависимости %s",
                            name, failed_deps
                        )
                    continue
                
                record.status = ComponentState.INITIALIZING
                
                try:
                    if hasattr(record.resource, 'initialize') and callable(record.resource.initialize):
                        result = await record.resource.initialize()
                    else:
                        # Если нет метода initialize, считаем успешным
                        result = True
                    
                    if result:
                        record.status = ComponentState.INITIALIZED
                        record.initialized_at = datetime.now()
                        results[name] = True
                        if self.event_bus_logger:
                            await self.event_bus_logger.debug("Ресурс '%s' успешно инициализирован", name)
                    else:
                        record.status = ComponentState.FAILED
                        record.init_error = "initialize returned False"
                        results[name] = False
                        if self.event_bus_logger:
                            await self.event_bus_logger.error("Ресурс '%s' вернул False при инициализации", name)
                            
                except Exception as e:
                    record.status = ComponentState.FAILED
                    record.init_error = str(e)
                    results[name] = False
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            "Ошибка инициализации ресурса '%s': %s", 
                            name, str(e), exc_info=True
                        )
                    await self._publish_event("resource_init_failed", {
                        "name": name, 
                        "error": str(e)
                    })

            self._initialized = True
            self._shutdown_in_progress = False
            
            success_count = sum(1 for v in results.values() if v)
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    "Все инфраструктурные ресурсы инициализированы: %d/%d успешно",
                    success_count, len(results)
                )
            
            await self._publish_event("lifecycle_initialized", {
                "total": len(results),
                "success": success_count
            })
            
            return results

    def _topological_sort(self, graph: Dict[str, set]) -> Optional[List[str]]:
        """
        Топологическая сортировка графа зависимостей (алгоритм Кана).
        
        ARGS:
        - graph: словарь {имя_ресурса: множество_зависимостей}
        
        RETURNS:
        - List[str]: порядок инициализации или None если есть цикл
        """
        # Подсчёт входящих степеней
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[node] += 1
        
        # Очередь узлов без входящих рёбер
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            # Уменьшение степени для зависимых узлов
            for other in graph:
                if node in graph[other]:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)
        
        # Если не все узлы обработаны → есть цикл
        if len(result) != len(graph):
            return None
        
        return result

    # ==================== ЗАВЕРШЕНИЕ РАБОТЫ ====================

    async def shutdown_all(self) -> Dict[str, bool]:
        """
        Завершение работы всех ресурсов в обратном порядке.
        
        Ресурсы завершаются в порядке, обратном инициализации
        (зависимые ресурсы завершаются раньше).
        
        RETURNS:
        - Dict[str, bool]: результаты завершения по каждому ресурсу
        """
        async with self._lock:
            if not self._initialized:
                return {}
            
            self._shutdown_in_progress = True

            if self.event_bus_logger:
                await self.event_bus_logger.info("Завершение работы инфраструктурных ресурсов")

            # Обратный порядок инициализации
            graph = {name: set(record.dependencies) for name, record in self._resources.items()}
            order = self._topological_sort(graph)
            shutdown_order = list(reversed(order)) if order else list(self._resources.keys())

            results = {}
            for name in shutdown_order:
                record = self._resources[name]
                
                if record.status == ComponentState.PENDING:
                    # Ресурс не был инициализирован, пропускаем
                    record.status = ComponentState.SHUTDOWN
                    results[name] = True
                    continue
                
                try:
                    if hasattr(record.resource, 'shutdown') and callable(record.resource.shutdown):
                        await record.resource.shutdown()
                    
                    record.status = ComponentState.SHUTDOWN
                    results[name] = True
                    
                    if self.event_bus_logger:
                        await self.event_bus_logger.debug("Ресурс '%s' завершён", name)
                        
                except Exception as e:
                    results[name] = False
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            "Ошибка при завершении ресурса '%s': %s", 
                            name, str(e), exc_info=True
                        )

            self._initialized = False
            self._shutdown_in_progress = False
            
            success_count = sum(1 for v in results.values() if v)
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    "Все инфраструктурные ресурсы завершены: %d/%d успешно",
                    success_count, len(results)
                )
            
            await self._publish_event("lifecycle_shutdown", {
                "total": len(results),
                "success": success_count
            })
            
            return results

    async def cleanup_all(self):
        """Завершение работы всех ресурсов (алиас для shutdown_all)."""
        await self.shutdown_all()

    # ==================== ПРОВЕРКА ЗДОРОВЬЯ ====================

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Выполняет health_check для всех ресурсов.
        
        RETURNS:
        - Dict[str, Dict[str, Any]]: результаты проверки по каждому ресурсу
        """
        results = {}
        for name, record in self._resources.items():
            try:
                if hasattr(record.resource, 'health_check') and callable(record.resource.health_check):
                    result = await record.resource.health_check()
                else:
                    result = {
                        "status": "unknown", 
                        "message": "health_check not implemented",
                        "resource_status": record.status.value
                    }
                results[name] = result
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        
        return results

    async def health_check_resource(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Проверка здоровья конкретного ресурса.
        
        ARGS:
        - name: имя ресурса
        
        RETURNS:
        - Dict[str, Any] или None если ресурс не найден
        """
        record = self._resources.get(name)
        if not record:
            return None
        
        try:
            if hasattr(record.resource, 'health_check') and callable(record.resource.health_check):
                return await record.resource.health_check()
            else:
                return {
                    "status": "unknown",
                    "message": "health_check not implemented",
                    "resource_status": record.status.value
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение ресурса по имени.
        
        ARGS:
        - name: имя ресурса
        
        RETURNS:
        - ресурс или None если не найден
        """
        record = self._resources.get(name)
        return record.resource if record else None

    def get_resources_by_type(self, resource_type: ResourceType) -> List[Any]:
        """
        Получение всех ресурсов определённого типа.
        
        ARGS:
        - resource_type: тип ресурсов
        
        RETURNS:
        - List[Any]: список ресурсов
        """
        return [
            record.resource 
            for record in self._resources.values() 
            if record.resource_type == resource_type
        ]

    def get_resource_record(self, name: str) -> Optional[ResourceRecord]:
        """
        Получение записи о ресурсе по имени.
        
        ARGS:
        - name: имя ресурса
        
        RETURNS:
        - ResourceRecord или None если не найден
        """
        return self._resources.get(name)

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики по ресурсам.
        
        RETURNS:
        - Dict[str, Any]: статистика
        """
        status_counts = {}
        type_counts = {}
        
        for record in self._resources.values():
            # Подсчёт по статусам
            status = record.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Подсчёт по типам
            rtype = record.resource_type.value
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
        
        return {
            "total_resources": len(self._resources),
            "initialized": self._initialized,
            "shutdown_in_progress": self._shutdown_in_progress,
            "by_status": status_counts,
            "by_type": type_counts,
        }

    def get_all_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение информации обо всех ресурсах.
        
        RETURNS:
        - Dict[str, Dict[str, Any]]: информация по каждому ресурсу
        """
        return {name: record.to_dict() for name, record in self._resources.items()}

    @property
    def resources_count(self) -> int:
        """Количество зарегистрированных ресурсов."""
        return len(self._resources)

    @property
    def initialized_count(self) -> int:
        """Количество инициализированных ресурсов."""
        return sum(
            1 for record in self._resources.values() 
            if record.status == ComponentState.INITIALIZED
        )

    @property
    def is_initialized(self) -> bool:
        """Статус инициализации менеджера."""
        return self._initialized

    @property
    def is_ready(self) -> bool:
        """Готов к работе (менеджер инициализирован)."""
        return self._initialized

    @property
    def state(self) -> ComponentState:
        """Общее состояние менеджера."""
        if not self._initialized:
            return ComponentState.CREATED
        if self._shutdown_in_progress:
            return ComponentState.SHUTDOWN
        return ComponentState.READY

    def get_components(self, component_type: ResourceType) -> List[Any]:
        """Получение всех компонентов определённого типа."""
        return self.get_resources_by_type(component_type)

    def get_all_components(self) -> Dict[ResourceType, List[Any]]:
        """Получение всех компонентов по типам."""
        result: Dict[ResourceType, List[Any]] = {}
        for record in self._resources.values():
            if record.resource_type not in (ResourceType.LLM, ResourceType.DATABASE, ResourceType.VECTOR,
                                             ResourceType.EMBEDDING, ResourceType.CACHE, ResourceType.STORAGE,
                                             ResourceType.COLLECTOR, ResourceType.DISCOVERY):
                if record.resource_type not in result:
                    result[record.resource_type] = []
                result[record.resource_type].append(record.resource)
        return result

    # ==================== ВНУТРЕННИЕ МЕТОДЫ ====================

    async def _publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Публикация события в шину событий."""
        if self.event_bus:
            try:
                await self.event_bus.publish(
                    event_type,
                    data=data,
                    source="LifecycleManager"
                )
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.debug("Ошибка публикации события: %s", e)
