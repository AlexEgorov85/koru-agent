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
import logging

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.models.enums.common_enums import ResourceType
from core.models.enums.component_status import ComponentStatus


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
    status: ComponentStatus = ComponentStatus.PENDING
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

    def __init__(
        self,
        event_bus: Optional[UnifiedEventBus] = None,
        log: Optional[logging.Logger] = None
    ):
        self._resources: Dict[str, ResourceRecord] = {}
        self._initialized = False
        self._shutdown_in_progress = False
        self.event_bus: Optional[UnifiedEventBus] = event_bus
        self.log = log or logging.getLogger(__name__)
        self._lock = asyncio.Lock()

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

            self.log.debug("Зарегистрирован ресурс '%s' типа %s",
                           name, resource_type.value,
                           extra={"event_type": EventType.SYSTEM_INIT})

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
                self.log.warning("LifecycleManager уже инициализирован",
                                 extra={"event_type": EventType.WARNING})
                return {name: True for name in self._resources}

            self.log.info("Начало инициализации %d инфраструктурных ресурсов",
                          len(self._resources),
                          extra={"event_type": EventType.SYSTEM_INIT})

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
                    record.status = ComponentStatus.FAILED
                    record.init_error = f"Failed dependencies: {failed_deps}"
                    results[name] = False
                    self.log.error("Ресурс '%s' не инициализирован: failed зависимости %s",
                                   name, failed_deps,
                                   extra={"event_type": EventType.SYSTEM_ERROR})
                    continue
                
                record.status = ComponentStatus.INITIALIZING
                
                try:
                    if hasattr(record.resource, 'initialize') and callable(record.resource.initialize):
                        result = await record.resource.initialize()
                    else:
                        # Если нет метода initialize, считаем успешным
                        result = True
                    
                    if result:
                        record.status = ComponentStatus.READY
                        record.initialized_at = datetime.now()
                        results[name] = True
                        self.log.debug("Ресурс '%s' успешно инициализирован", name,
                                       extra={"event_type": EventType.SYSTEM_INIT})
                    else:
                        record.status = ComponentStatus.FAILED
                        record.init_error = "initialize returned False"
                        results[name] = False
                        self.log.error("Ресурс '%s' вернул False при инициализации", name,
                                       extra={"event_type": EventType.SYSTEM_ERROR})
                            
                except Exception as e:
                    record.status = ComponentStatus.FAILED
                    record.init_error = str(e)
                    results[name] = False
                    self.log.error("Ошибка инициализации ресурса '%s': %s",
                                   name, str(e),
                                   extra={"event_type": EventType.SYSTEM_ERROR}, exc_info=True)
                    await self._publish_event("resource_init_failed", {
                        "name": name, 
                        "error": str(e)
                    })

            self._initialized = True
            self._shutdown_in_progress = False

            success_count = sum(1 for v in results.values() if v)
            self.log.info("Все инфраструктурные ресурсы инициализированы: %d/%d успешно",
                          success_count, len(results),
                          extra={"event_type": EventType.SYSTEM_READY})
            
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

            self.log.info("Завершение работы инфраструктурных ресурсов",
                          extra={"event_type": EventType.SYSTEM_SHUTDOWN})

            # Обратный порядок инициализации
            graph = {name: set(record.dependencies) for name, record in self._resources.items()}
            order = self._topological_sort(graph)
            shutdown_order = list(reversed(order)) if order else list(self._resources.keys())

            results = {}
            for name in shutdown_order:
                record = self._resources[name]
                
                if record.status == ComponentStatus.PENDING:
                    # Ресурс не был инициализирован, пропускаем
                    record.status = ComponentStatus.SHUTDOWN
                    results[name] = True
                    continue
                
                try:
                    if hasattr(record.resource, 'shutdown') and callable(record.resource.shutdown):
                        await record.resource.shutdown()
                    
                    record.status = ComponentStatus.SHUTDOWN
                    results[name] = True

                    self.log.debug("Ресурс '%s' завершён", name,
                                   extra={"event_type": EventType.SYSTEM_SHUTDOWN})

                except Exception as e:
                    results[name] = False
                    self.log.error("Ошибка при завершении ресурса '%s': %s",
                                   name, str(e),
                                   extra={"event_type": EventType.SYSTEM_ERROR}, exc_info=True)

            self._initialized = False
            self._shutdown_in_progress = False

            success_count = sum(1 for v in results.values() if v)
            self.log.info("Все инфраструктурные ресурсы завершены: %d/%d успешно",
                          success_count, len(results),
                          extra={"event_type": EventType.SYSTEM_SHUTDOWN})
            
            await self._publish_event("lifecycle_shutdown", {
                "total": len(results),
                "success": success_count
            })
            
            return results

    async def cleanup_all(self):
        """Завершение работы всех ресурсов (алиас для shutdown_all)."""
        await self.shutdown_all()

    async def clear_resources(self) -> None:
        """
        Очистка всех зарегистрированных ресурсов.
        
        Вызывается после shutdown_all() для подготовки менеджера
        к повторной регистрации ресурсов (например, при создании
        нового ApplicationContext).
        
        NOTE: Безопасно вызывать только после shutdown_all().
        """
        async with self._lock:
            self._resources.clear()
            await self._publish_event("resources_cleared", {})

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
            if record.status == ComponentStatus.READY
        )

    @property
    def is_initialized(self) -> bool:
        """Статус инициализации менеджера."""
        return self._initialized

    @property
    def is_ready(self) -> bool:
        """Готов к работе (менеджер инициализирован)."""
        return self._initialized

    def get_dashboard_info(self) -> Dict[str, Any]:
        """
        Получение информации для дашборда админки.
        
        RETURNS:
        - Dict с категориями: llm_providers, db_providers, services, skills, tools, patterns
        """
        result = {
            "llm_providers": [],
            "db_providers": [],
            "services": [],
            "skills": [],
            "tools": [],
            "patterns": []
        }

        for record in self._resources.values():
            rtype_str = str(record.resource_type)
            
            # Базовая информация о компоненте
            comp_info = {
                "name": record.name,
                "status": record.status.value,
                "description": "",
                "capabilities": [],
                "prompts": [],
                "contracts": [],
                "component_type": rtype_str
            }

            # Описание из metadata или компонента
            if record.metadata and "description" in record.metadata:
                comp_info["description"] = record.metadata["description"]
            elif hasattr(record.resource, "description"):
                comp_info["description"] = record.resource.description

            # Дополнительная инфо для LLM провайдеров
            if rtype_str == str(ResourceType.LLM):
                # Сначала пробуем из metadata
                if record.metadata and "model_name" in record.metadata:
                    comp_info["description"] = f"модель: {record.metadata['model_name']}"
                # Потом из компонента
                if not comp_info["description"] and hasattr(record.resource, "model_name"):
                    comp_info["description"] = f"модель: {record.resource.model_name}"

            # Дополнительная инфо для DB провайдеров
            if rtype_str == str(ResourceType.DATABASE):
                if record.metadata:
                    if "db_path" in record.metadata:
                        comp_info["description"] = f"путь: {record.metadata['db_path']}"
                    elif "database" in record.metadata:
                        host = record.metadata.get("host", "localhost")
                        port = record.metadata.get("port", 5432)
                        db = record.metadata.get("database", "unknown")
                        comp_info["description"] = f"{host}:{port}/{db}"

            # Capabilities
            if hasattr(record.resource, "get_capabilities"):
                try:
                    caps = record.resource.get_capabilities()
                    if caps:
                        for c in caps:
                            comp_info["capabilities"].append({
                                "name": c.name,
                                "description": getattr(c, "description", "")
                            })
                except:
                    pass

            # Промпты из компонента (реальные данные)
            if hasattr(record.resource, "prompts") and record.resource.prompts:
                for cap_name, prompt_obj in record.resource.prompts.items():
                    stat = "active"
                    if hasattr(prompt_obj, "status"):
                        stat = prompt_obj.status.value if hasattr(prompt_obj.status, 'value') else str(prompt_obj.status)
                    version = getattr(prompt_obj, "version", "unknown")
                    comp_info["prompts"].append({
                        "capability": cap_name,
                        "version": version,
                        "status": stat
                    })

            # Контракты из компонента - читаем из resolved_* в component_config
            cfg = None
            if hasattr(record.resource, "component_config") and record.resource.component_config:
                cfg = record.resource.component_config
            
            seen_contracts = set()
            
            # Input contracts из resolved_input_contracts
            if cfg and hasattr(cfg, "resolved_input_contracts") and cfg.resolved_input_contracts:
                for cap_name, contract_obj in cfg.resolved_input_contracts.items():
                    key = f"input:{cap_name}"
                    if key not in seen_contracts:
                        seen_contracts.add(key)
                        version = getattr(contract_obj, "version", "unknown") if contract_obj else "unknown"
                        comp_type = getattr(contract_obj, "component_type", "unknown") if contract_obj else "unknown"
                        comp_info["contracts"].append({
                            "capability": cap_name,
                            "version": version,
                            "status": "active",
                            "direction": "input",
                            "component_type": str(comp_type) if comp_type else "unknown"
                        })
            
            # Output contracts из resolved_output_contracts
            if cfg and hasattr(cfg, "resolved_output_contracts") and cfg.resolved_output_contracts:
                for cap_name, contract_obj in cfg.resolved_output_contracts.items():
                    key = f"output:{cap_name}"
                    if key not in seen_contracts:
                        seen_contracts.add(key)
                        version = getattr(contract_obj, "version", "unknown") if contract_obj else "unknown"
                        comp_type = getattr(contract_obj, "component_type", "unknown") if contract_obj else "unknown"
                        comp_info["contracts"].append({
                            "capability": cap_name,
                            "version": version,
                            "status": "active",
                            "direction": "output",
                            "component_type": str(comp_type) if comp_type else "unknown"
                        })

            # Группировка по типу
            if rtype_str == str(ResourceType.LLM):
                result["llm_providers"].append(comp_info)
            elif rtype_str == str(ResourceType.DATABASE):
                result["db_providers"].append(comp_info)
            elif rtype_str == str(ResourceType.SERVICE):
                result["services"].append(comp_info)
            elif rtype_str == str(ResourceType.SKILL):
                result["skills"].append(comp_info)
            elif rtype_str == str(ResourceType.TOOL):
                result["tools"].append(comp_info)
            elif rtype_str == str(ResourceType.BEHAVIOR):
                result["patterns"].append(comp_info)

        return result

    @property
    def state(self) -> ComponentStatus:
        """Общее состояние менеджера."""
        if not self._initialized:
            return ComponentStatus.CREATED
        if self._shutdown_in_progress:
            return ComponentStatus.SHUTDOWN
        return ComponentStatus.READY

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
                self.log.debug("Ошибка публикации события: %s", e,
                               extra={"event_type": EventType.DEBUG})
