"""
Прикладной контекст - версионируемый контекст для сессии/агента.

СОДЕРЖИТ:
- ComponentRegistry: сервисы, навыки, инструменты, behavior patterns
- Конфигурацию: AppConfig, флаги (side_effects_enabled, detailed_metrics)
- Ссылку на InfrastructureContext (только для чтения)

ЖИЗНЕННЫЙ ЦИКЛ:
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
"""
import logging
import uuid
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal, Type

from pydantic import BaseModel

from core.agent.components.action_executor import ActionExecutor
from core.agent.components.component_factory import ComponentFactory
from core.application_context.base_system_context import BaseSystemContext
from core.config.component_config import ComponentConfig
from core.infrastructure.logging.logger import EventBusLogger
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.enums.common_enums import ComponentType, ResourceType
from core.components.services.data_repository import DataRepository
from core.components.services.registry.component_registry import ComponentRegistry


class ApplicationContext(BaseSystemContext):
    """Версионируемый контекст приложения. Создаётся на сессию/агента."""

    def __init__(
        self,
        infrastructure_context: InfrastructureContext,
        config: Optional['AppConfig'] = None,
        profile: Literal["prod", "sandbox"] = "prod",
        lifecycle_manager: Optional[Any] = None,
        prompt_loading_config: Optional[Dict[str, str]] = None
    ):
        """
        Инициализация прикладного контекста.

        ПАРАМЕТРЫ:
        - infrastructure_context: Инфраструктурный контекст (только для чтения!)
        - config: Единая конфигурация приложения (AppConfig). Если None, будет создана автоматически.
        - profile: Профиль работы ('prod' или 'sandbox')
        - lifecycle_manager: Общий менеджер жизненного цикла (опционально)
        - prompt_loading_config: Конфигурация загрузки промтов.
            Формат: {"capability": "active"|"draft", "default": "active"|"draft"}
            Пример: {"behavior.react.think": "draft", "default": "active"}
            Если None - загружаются только active промты.
        """
        from core.config.app_config import AppConfig

        self.id = str(uuid.uuid4())
        self.infrastructure_context = infrastructure_context
        self.profile = profile
        self._prompt_overrides: Dict[str, str] = {}
        self._prompt_loading_config = prompt_loading_config or {}

        if lifecycle_manager is not None:
            self.lifecycle_manager = lifecycle_manager
        elif hasattr(infrastructure_context, 'lifecycle_manager'):
            self.lifecycle_manager = infrastructure_context.lifecycle_manager
        else:
            self.lifecycle_manager = None

        if config is None:
            self.config = AppConfig(config_id=f"auto_{profile}_{infrastructure_context.id[:8]}")
        else:
            self.config = config

        self.components = ComponentRegistry()
        self.side_effects_enabled = getattr(self.config, 'side_effects_enabled', True)
        self.detailed_metrics = getattr(self.config, 'detailed_metrics', False)

        self.event_bus_logger = None
        self._init_event_bus_logger()

        data_dir = getattr(infrastructure_context.config, 'data_dir', 'data')
        self._data_dir = Path(data_dir)
        self.data_repository = None
        self.llm_orchestrator = None
        self._initialized = False

    @property
    def is_ready(self) -> bool:
        """Проверка готовности контекста."""
        return self.lifecycle_manager is not None and self.lifecycle_manager.is_ready

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации контекста."""
        return self._initialized

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        if hasattr(self, 'infrastructure_context') and self.infrastructure_context:
            event_bus = getattr(self.infrastructure_context, 'event_bus', None)
            if event_bus:
                self.event_bus_logger = EventBusLogger(
                    event_bus,
                    session_id=str(self.infrastructure_context.id),
                    agent_id="system",
                    component=self.__class__.__name__
                )
        self.logger = logging.getLogger(f"ApplicationContext.{self.id}")

    def _get_resource_type_for_component(self, component_type: ComponentType) -> ResourceType:
        """Преобразование ComponentType в ResourceType для LifecycleManager."""
        mapping = {
            ComponentType.SERVICE: ResourceType.SERVICE,
            ComponentType.SKILL: ResourceType.SKILL,
            ComponentType.TOOL: ResourceType.TOOL,
            ComponentType.BEHAVIOR: ResourceType.BEHAVIOR,
        }
        return mapping.get(component_type, ResourceType.OTHER)

    def _resolve_component_configs(self) -> Dict[ComponentType, Dict[str, Any]]:
        """ЕДИНЫЙ источник конфигурации для всех компонентов."""
        return {
            ComponentType.SERVICE: getattr(self.config, 'service_configs', {}),
            ComponentType.SKILL: getattr(self.config, 'skill_configs', {}),
            ComponentType.TOOL: getattr(self.config, 'tool_configs', {}),
            ComponentType.BEHAVIOR: getattr(self.config, 'behavior_configs', {}),
        }

    def _resolve_component_class(self, component_type: ComponentType, name: str) -> type:
        """Разрешение класса компонента по имени и типу."""
        factory = ComponentFactory(self.infrastructure_context)
        return factory._resolve_component_class(component_type.value, name)

    async def _create_component(self, component_type: ComponentType, name: str, config: Any, executor: 'ActionExecutor') -> 'BaseComponent':
        """ЕДИНЫЙ фабричный метод для создания ЛЮБОГО компонента."""
        factory = ComponentFactory(self.infrastructure_context)
        component_type_str = component_type.value

        if not isinstance(config, ComponentConfig):
            config = ComponentConfig(
                variant_id=f"{name}_default",
                prompt_versions=getattr(config, 'prompt_versions', {}),
                input_contract_versions=getattr(config, 'input_contract_versions', {}),
                output_contract_versions=getattr(config, 'output_contract_versions', {}),
                side_effects_enabled=getattr(config, 'side_effects_enabled', True),
                detailed_metrics=getattr(config, 'detailed_metrics', False),
                parameters=getattr(config, 'parameters', {}),
                dependencies=getattr(config, 'dependencies', [])
            )

        component = await factory.create_by_name(
            component_type=component_type_str,
            name=name,
            application_context=self,
            component_config=config,
            executor=executor
        )
        return component

    def initialize_sync(self) -> bool:
        """Синхронная инициализация. Безопасна для вызова из sync и async контекста."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(self.initialize()))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.initialize())

    async def initialize(self) -> bool:
        """Жизненный цикл инициализации: репозиторий → компоненты → инициализация."""
        if self._initialized:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("ApplicationContext уже инициализирован")
            else:
                self.logger.warning("ApplicationContext уже инициализирован")
            return True

        if not self.lifecycle_manager:
            self.lifecycle_manager = self.infrastructure_context.lifecycle_manager
        if not self.lifecycle_manager:
            raise RuntimeError("InfrastructureContext.lifecycle_manager не инициализирован")

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Начало инициализации ApplicationContext {self.id}")
        else:
            self.logger.info(f"Начало инициализации ApplicationContext {self.id}")

        if hasattr(self.config, 'config_id') and self.config.config_id.startswith('auto_'):
            await self._auto_fill_config()

        if not self.data_repository:
            from core.infrastructure.storage.file_system_data_source import FileSystemDataSource

            discovery = self.infrastructure_context.get_resource_discovery()
            registry_config = {
                'capability_types': {},
                'active_prompts': {p.capability: p.version for p in discovery.discover_prompts()},
                'active_contracts': {}
            }
            for contract in discovery.discover_contracts():
                cap = contract.capability
                if cap not in registry_config['active_contracts']:
                    registry_config['active_contracts'][cap] = {}
                registry_config['active_contracts'][cap][contract.direction.value] = contract.version

            fs_data_source = FileSystemDataSource(self._data_dir, registry_config)
            fs_data_source.initialize()

            self.data_repository = DataRepository(
                fs_data_source,
                profile=self.profile,
                event_bus=self.infrastructure_context.event_bus,
                prompt_loading_config=self._prompt_loading_config,
            )

        if not await self.data_repository.initialize(self.config):
            self.logger.critical(
                f"КРИТИЧЕСКАЯ ОШИБКА СТРУКТУРЫ ДАННЫХ:\n"
                f"{self.data_repository.get_validation_report()}\n"
                f"Система НЕ БУДЕТ запущена с неконсистентной конфигурацией."
            )
            return False

        self.logger.info(
            f"DataRepository инициализирован успешно:\n"
            f"{self.data_repository.get_validation_report()}"
        )

        executor = ActionExecutor(self)

        try:
            from core.infrastructure.providers.llm.llm_orchestrator import LLMOrchestrator
            print("[ApplicationContext] Создание LLMOrchestrator...", flush=True)
            self.llm_orchestrator = LLMOrchestrator(
                event_bus=self.infrastructure_context.event_bus,
                cleanup_interval=600.0,
                max_pending_calls=100
            )
            print("[ApplicationContext] Вызов llm_orchestrator.initialize()...", flush=True)
            await self.llm_orchestrator.initialize()
            print("[ApplicationContext] LLMOrchestrator инициализирован успешно!", flush=True)
            self.logger.info("LLMOrchestrator инициализирован")
        except Exception as e:
            print(f"[ApplicationContext] ОШИБКА инициализации LLMOrchestrator: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.logger.error(f"Ошибка инициализации LLMOrchestrator: {e}")
            from core.errors.exceptions import ComponentInitializationError
            raise ComponentInitializationError(
                f"Не удалось инициализировать LLMOrchestrator: {e}. "
                f"LLMOrchestrator критически важен для работы системы.",
                component="llm_orchestrator"
            )

        self.logger.info("Начало создания компонентов...")
        component_configs = self._resolve_component_configs()
        self.logger.info(f"Конфигурации компонентов: {[(k.value, list(v.keys())) for k, v in component_configs.items() if v]}")
        components_created = 0
        for comp_type, configs in component_configs.items():
            if not configs:
                continue
            self.logger.info(f"Обработка типа компонента {comp_type.value}: {list(configs.keys())}")
            for name, enriched_config in configs.items():
                self.logger.info(f"Создание компонента {comp_type.value}.{name}...")
                try:
                    component = await self._create_component(comp_type, name, enriched_config, executor)
                    self.logger.info(f"Регистрация компонента {comp_type.value}.{name}...")
                    self.components.register(comp_type, name, component)

                    resource_type = self._get_resource_type_for_component(comp_type)
                    await self.lifecycle_manager.register_component(
                        name=name,
                        component=component,
                        component_type=resource_type
                    )
                    components_created += 1
                    self.logger.info(f"Компонент {comp_type.value}.{name} создан и зарегистрирован")
                    if self.infrastructure_context and self.infrastructure_context.event_bus:
                        await self.infrastructure_context.event_bus.publish(
                            event_type="component.registered",
                            data={
                                "component_type": comp_type.value,
                                "name": name,
                                "class": component.__class__.__name__
                            },
                            source="application_context",
                            session_id="system"
                        )
                except Exception as e:
                    self.logger.error(f"Ошибка создания {comp_type.value}.{name}: {e}", exc_info=True)
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    if self.infrastructure_context and self.infrastructure_context.event_bus:
                        await self.infrastructure_context.event_bus.publish(
                            event_type="component.create_failed",
                            data={
                                "component_type": comp_type.value,
                                "name": name,
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            },
                            source="application_context",
                            session_id="system"
                        )

        self.logger.info(f"Создано {components_created} компонентов")

        success = await self._initialize_components_with_dependencies()
        if not success:
            self.logger.error("Ошибка инициализации компонентов с учетом зависимостей")
            return False

        if not await self._verify_readiness():
            return False

        await self.lifecycle_manager.initialize_all()
        self._initialized = True
        if self.infrastructure_context and self.infrastructure_context.event_bus:
            await self.infrastructure_context.event_bus.publish(
                EventType.USER_RESULT,
                data={"message": f"ApplicationContext инициализирован (profile={self.profile})", "icon": "✅"},
                session_id=str(self.infrastructure_context.id),
            )
        self.logger.info(f"ApplicationContext {self.id} успешно инициализирован")
        return True

    async def _initialize_components_with_dependencies(self) -> bool:
        """Инициализация компонентов с учетом зависимостей (топологическая сортировка)."""
        self.logger.info("=== НАЧАЛО _initialize_components_with_dependencies ===")
        from collections import defaultdict, deque

        all_components = self.components.all_components()
        component_map = {comp.name: comp for comp in all_components}
        dependency_graph = defaultdict(list)
        dependents_graph = defaultdict(list)

        for component in all_components:
            deps = []
            if hasattr(component, 'DEPENDENCIES'):
                deps = getattr(component, 'DEPENDENCIES', [])
            elif hasattr(component, 'dependencies'):
                deps = getattr(component, 'dependencies', [])
            dependency_graph[component.name] = deps[:]
            for dep in deps:
                dependents_graph[dep].append(component.name)

        in_degree = {comp.name: 0 for comp in all_components}
        for component_name in dependency_graph:
            for dep_name in dependency_graph[component_name]:
                if dep_name in in_degree:
                    in_degree[component_name] += 1

        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        initialization_order = []

        while queue:
            current_component_name = queue.popleft()
            initialization_order.append(current_component_name)
            for dependent_name in dependents_graph[current_component_name]:
                if dependent_name in in_degree:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        queue.append(dependent_name)

        if len(initialization_order) != len(all_components):
            remaining_components = set(in_degree.keys()) - set(initialization_order)
            self.logger.error(f"Обнаружена циклическая зависимость между компонентами: {remaining_components}")
            all_initialized_names = set(initialization_order)
            for comp in all_components:
                if comp.name not in all_initialized_names:
                    initialization_order.append(comp.name)

        initialized_components = set()
        for component_name in initialization_order:
            if component_name not in component_map:
                continue
            component = component_map[component_name]
            try:
                if hasattr(component, 'initialize') and callable(component.initialize):
                    if await component.initialize():
                        initialized_components.add(component.name)
                        if self.infrastructure_context and self.infrastructure_context.event_bus:
                            await self.infrastructure_context.event_bus.publish(
                                event_type="component.initialized",
                                data={"name": component.name, "class": component.__class__.__name__},
                                source="application_context",
                                session_id="system"
                            )
                    else:
                        self.logger.error(f"Компонент {component.name} не смог инициализироваться")
                        if self.infrastructure_context and self.infrastructure_context.event_bus:
                            await self.infrastructure_context.event_bus.publish(
                                event_type="component.init_failed",
                                data={"name": component.name, "reason": "initialize() returned False"},
                                source="application_context",
                                session_id="system"
                            )
                        return False
                else:
                    initialized_components.add(component.name)
                    if self.infrastructure_context and self.infrastructure_context.event_bus:
                        await self.infrastructure_context.event_bus.publish(
                            event_type="component.initialized",
                            data={"name": component.name, "class": component.__class__.__name__, "note": "no initialize method"},
                            source="application_context",
                            session_id="system"
                        )
            except Exception as e:
                self.logger.error(f"Ошибка при инициализации компонента {component.name}: {e}")
                import traceback
                if self.infrastructure_context and self.infrastructure_context.event_bus:
                    await self.infrastructure_context.event_bus.publish(
                        event_type="component.init_failed",
                        data={"name": component.name, "error": str(e), "traceback": traceback.format_exc()},
                        source="application_context",
                        session_id="system"
                    )
                return False

        all_names = {comp.name for comp in all_components}
        if len(initialized_components) != len(all_names):
            uninitialized = all_names - initialized_components
            self.logger.error(f"Не все компоненты были инициализированы: {uninitialized}")
            if self.infrastructure_context and self.infrastructure_context.event_bus:
                await self.infrastructure_context.event_bus.publish(
                    event_type="component.init_partial",
                    data={"uninitialized": list(uninitialized)},
                    source="application_context",
                    session_id="system"
                )
            return False

        return True

    async def _verify_readiness(self) -> bool:
        """Валидация, что ВСЕ компоненты готовы к работе."""
        declared_components = self._resolve_component_configs()
        for comp_type, names in declared_components.items():
            for name in names:
                component = self.components.get(comp_type, name)
                if component is None:
                    self.logger.error(f"Компонент {comp_type.value}.{name} не найден")
                    return False
                if hasattr(component, 'is_initialized') and callable(component.is_initialized):
                    if not component.is_initialized():
                        self.logger.error(f"Компонент {comp_type.value}.{name} не инициализирован")
                        return False
                elif hasattr(component, '_initialized'):
                    if not component._initialized:
                        self.logger.error(f"Компонент {comp_type.value}.{name} не инициализирован")
                        return False
                elif hasattr(component, 'is_ready') and callable(component.is_ready):
                    if not component.is_ready():
                        self.logger.error(f"Компонент {component.name} не готов к работе")
                        return False
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности контекста и всех компонентов."""
        import time
        start_time = time.time()

        health_report = {
            'context_id': self.id,
            'timestamp': time.time(),
            'profile': self.profile,
            'overall_status': 'healthy',
            'components_health': {},
            'metrics': {
                'total_components': 0,
                'healthy_components': 0,
                'unhealthy_components': 0,
                'initialization_time': 0
            },
            'details': {}
        }

        context_healthy = self.is_initialized
        health_report['context_healthy'] = context_healthy
        if not context_healthy:
            health_report['overall_status'] = 'unhealthy'
            health_report['details']['context_error'] = 'ApplicationContext не инициализирован'

        all_components = self.components.all_components()
        health_report['metrics']['total_components'] = len(all_components)

        for component in all_components:
            comp_health = {
                'name': component.name,
                'type': type(component).__name__,
                'initialized': getattr(component, '_initialized', False),
                'ready': True,
                'resource_status': {
                    'prompts_loaded': len(getattr(component, '_cached_prompts', {})),
                    'input_contracts_loaded': len(getattr(component, '_cached_input_contracts', {})),
                    'output_contracts_loaded': len(getattr(component, '_cached_output_contracts', {}))
                }
            }

            if hasattr(component, '_initialized'):
                comp_health['initialized'] = component._initialized
                comp_health['ready'] = component._initialized
            else:
                comp_health['ready'] = True

            if hasattr(component, '_dependencies'):
                comp_health['dependencies_count'] = len(component._dependencies)
                comp_health['dependencies'] = list(component._dependencies.keys())

            if not comp_health['ready']:
                comp_health['status'] = 'unhealthy'
                health_report['overall_status'] = 'unhealthy'
                health_report['metrics']['unhealthy_components'] += 1
            else:
                comp_health['status'] = 'healthy'
                health_report['metrics']['healthy_components'] += 1

            health_report['components_health'][component.name] = comp_health

        if health_report['metrics']['unhealthy_components'] > 0:
            health_report['overall_status'] = 'degraded' if health_report['metrics']['unhealthy_components'] < health_report['metrics']['total_components'] else 'unhealthy'
        elif health_report['metrics']['healthy_components'] == 0:
            health_report['overall_status'] = 'unhealthy'

        health_report['metrics']['check_duration'] = time.time() - start_time
        self.logger.info(f"Health check completed: {health_report['overall_status']}, "
                         f"{health_report['metrics']['healthy_components']}/{health_report['metrics']['total_components']} components healthy")
        return health_report

    def get_behavior_pattern(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.BEHAVIOR, name)

    def get_service(self, name: str) -> Optional[Any]:
        """Получение сервиса по имени."""
        return self.components.get(ComponentType.SERVICE, name)

    async def _validate_versions_by_profile(self, prompt_versions: dict, input_contract_versions: dict = None, output_contract_versions: dict = None) -> bool:
        """Валидация версий в зависимости от профиля и prompt_loading_config."""
        from core.errors.exceptions import ComponentInitializationError

        if prompt_versions:
            try:
                data_repo = self.data_repository
                for capability, version in prompt_versions.items():
                    try:
                        prompt_obj = await data_repo.get_prompt(capability, version)
                        status = None
                        if hasattr(prompt_obj, 'status'):
                            status_obj = prompt_obj.status
                            status = status_obj.value if hasattr(status_obj, 'value') else str(status_obj)
                        elif hasattr(prompt_obj, 'metadata') and hasattr(prompt_obj.metadata, 'status'):
                            status_obj = prompt_obj.metadata.status
                            status = status_obj.value if hasattr(status_obj, 'value') else str(status_obj)

                        if status is None:
                            raise ComponentInitializationError(
                                f"Не удалось получить статус для промпта {capability}@{version}."
                            )

                        if self._prompt_loading_config:
                            needed_status = self._prompt_loading_config.get(
                                capability,
                                self._prompt_loading_config.get('default', 'active')
                            )
                            if status != needed_status:
                                all_prompts = data_repo.get_prompt_versions(capability)
                                found_correct = False
                                for p in all_prompts:
                                    p_status = getattr(p, 'status', None)
                                    if hasattr(p_status, 'value'):
                                        p_status = p_status.value
                                    if str(p_status) == needed_status:
                                        prompt_versions[capability] = p.version
                                        found_correct = True
                                        break
                                if not found_correct:
                                    raise ComponentInitializationError(
                                        f"[CONFIG] Промпт {capability}@{version} имеет статус '{status}', "
                                        f"но требуется '{needed_status}'."
                                    )
                        else:
                            if self.profile == "prod" and status != "active":
                                raise ComponentInitializationError(
                                    f"[PROD] Промпт версия {capability}@{version} имеет статус '{status}', "
                                    f"но требуется 'active'."
                                )
                            elif self.profile == "sandbox" and status == "archived":
                                raise ComponentInitializationError(
                                    f"[SANDBOX] Промпт версия {capability}@{version} архивирована. "
                                    f"Использование архивированных версий запрещено."
                                )
                    except ComponentInitializationError:
                        raise
                    except Exception as e:
                        raise ComponentInitializationError(
                            f"Не удалось загрузить или получить статус для промпта {capability}@{version}: {e}"
                        )
            except ComponentInitializationError:
                raise
            except Exception as e:
                raise ComponentInitializationError(f"Ошибка при доступе к хранилищу промптов: {e}")

        if input_contract_versions:
            try:
                contract_repository = self.infrastructure_context.get_contract_storage()
                for capability, version in input_contract_versions.items():
                    try:
                        exists = await contract_repository.exists(capability, version, "input")
                        if not exists:
                            raise ComponentInitializationError(
                                f"[{self.profile.upper()}] Входной контракт {capability}@{version} не существует."
                            )
                        await contract_repository.load(capability, version, "input")
                    except ComponentInitializationError:
                        raise
                    except Exception as e:
                        raise ComponentInitializationError(
                            f"Не удалось загрузить входной контракт {capability}@{version}: {e}"
                        )
            except ComponentInitializationError:
                raise
            except Exception as e:
                raise ComponentInitializationError(
                    f"Хранилище контрактов недоступно при валидации входных контрактов: {e}"
                )

        if output_contract_versions:
            try:
                contract_repository = self.infrastructure_context.get_contract_storage()
                for capability, version in output_contract_versions.items():
                    try:
                        exists = await contract_repository.exists(capability, version, "output")
                        if not exists:
                            raise ComponentInitializationError(
                                f"[{self.profile.upper()}] Выходной контракт {capability}@{version} не существует."
                            )
                        await contract_repository.load(capability, version, "output")
                    except ComponentInitializationError:
                        raise
                    except Exception as e:
                        raise ComponentInitializationError(
                            f"Не удалось загрузить выходной контракт {capability}@{version}: {e}"
                        )
            except ComponentInitializationError:
                raise
            except Exception as e:
                raise ComponentInitializationError(
                    f"Хранилище контрактов недоступно при валидации выходных контрактов: {e}"
                )

        return True

    @classmethod
    async def create_prod_auto(cls, infrastructure_context, profile="prod"):
        """Создание продакшен контекста с автоматически сгенерированной конфигурацией."""
        from core.config.app_config import AppConfig
        empty_config = AppConfig(config_id=f"auto_prod_{infrastructure_context.id[:8]}")
        context = cls(
            infrastructure_context=infrastructure_context,
            config=empty_config,
            profile=profile
        )
        await context._auto_fill_config()
        return context

    async def _auto_fill_config(self):
        """Автоматическое заполнение конфигурации через AppConfig.from_discovery()."""
        discovery = self.infrastructure_context.get_resource_discovery()
        self.config = type(self.config).from_discovery(
            profile=self.profile,
            data_dir=str(self._data_dir),
            discovery=discovery,
        )

    def get_prompt(self, capability: str, version: Optional[str] = None) -> str:
        """Получение текста промпта через DataRepository."""
        # Проверяем переопределённые промпты (из optimize)
        content_overrides = getattr(self.config, '_prompt_content_overrides', {})
        if capability in content_overrides:
            return content_overrides[capability]

        if self.data_repository:
            if version is None:
                version = self.config.prompt_versions.get(capability)
                if version is None:
                    for comp_type in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
                        if hasattr(self.config, comp_type):
                            comp_configs = getattr(self.config, comp_type)
                            for _, comp_config in comp_configs.items():
                                if hasattr(comp_config, 'prompt_versions') and capability in comp_config.prompt_versions:
                                    version = comp_config.prompt_versions[capability]
                                    break
                    if version is None:
                        self.logger.warning(
                            f"Промпт '{capability}' не найден в конфигурации (версия не указана). "
                            f"Возвращаем пустую строку."
                        )
                        return ""

            if version:
                try:
                    prompt_obj = self.data_repository.get_prompt(capability, version)
                    return prompt_obj.content
                except Exception as e:
                    self.logger.error(
                        f"Ошибка получения промпта '{capability}@{version}': {e}. "
                        f"Возвращаем пустую строку."
                    )
                    return ""
        return ""

    def get_input_contract_schema(self, capability: str, version: Optional[str] = None) -> Type[BaseModel]:
        """Возвращает скомпилированную схему для валидации входных данных."""
        if self.data_repository:
            if version is None:
                version = self.config.input_contract_versions.get(capability)
                if version is None:
                    version = self.config.input_contract_versions.get(capability + ".input")
                if version is None:
                    for comp_type in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
                        if hasattr(self.config, comp_type):
                            comp_configs = getattr(self.config, comp_type)
                            for _, comp_config in comp_configs.items():
                                if hasattr(comp_config, 'input_contract_versions'):
                                    if capability in comp_config.input_contract_versions:
                                        version = comp_config.input_contract_versions[capability]
                                        break
                                    elif capability + ".input" in comp_config.input_contract_versions:
                                        version = comp_config.input_contract_versions[capability + ".input"]
                                        break
                    if version is None:
                        return BaseModel

            if version:
                try:
                    return self.data_repository.get_contract_schema(capability, version, "input")
                except Exception:
                    return BaseModel
        return BaseModel

    def get_resource(self, name: str):
        """Получение ресурса — ищет в компонентах, затем в инфраструктурном контексте."""
        service = self.components.get(ComponentType.SERVICE, name)
        if service:
            return service
        tool = self.components.get(ComponentType.TOOL, name)
        if tool:
            return tool
        skill = self.components.get(ComponentType.SKILL, name)
        if skill:
            return skill
        return self.infrastructure_context.get_resource(name)

    def set_prompt_override(self, capability: str, version: str):
        """Установка оверрайда версии промпта (только для песочницы)."""
        if self.profile != "sandbox":
            raise RuntimeError("Оверрайды версий разрешены ТОЛЬКО в режиме песочницы")

        prompt_path = self._data_dir / "prompts" / capability / f"{version}.yaml"
        if not prompt_path.exists():
            prompt_path_json = self._data_dir / "prompts" / capability / f"{version}.json"
            if not prompt_path_json.exists():
                raise ValueError(f"Версия {capability}@{version} не существует")

        self._prompt_overrides[capability] = version
        self.logger.info(f"Установлен оверрайд: {capability}@{version} для песочницы")

    async def clone_with_prompt_content_override(
        self,
        capability: str,
        prompt_content: str,
    ) -> 'ApplicationContext':
        """
        Создание нового контекста с переопределённым содержанием промпта.

        Используется при оптимизации: для каждого кандидата создаётся
        отдельный sandbox контекст с модифицированным промптом.

        ARGS:
        - capability: имя capability (например 'book_library.search_books')
        - prompt_content: новое содержание промпта

        RETURNS:
        - ApplicationContext: новый контекст с переопределённым промптом
        """
        from copy import deepcopy

        new_config = deepcopy(self.config)

        content_overrides = getattr(new_config, '_prompt_content_overrides', {})
        content_overrides[capability] = prompt_content
        new_config._prompt_content_overrides = content_overrides

        # Очищаем ресурсы перед созданием нового контекста
        if self.lifecycle_manager:
            await self.lifecycle_manager.clear_resources()

        new_ctx = ApplicationContext(
            infrastructure_context=self.infrastructure_context,
            config=new_config,
            profile=self.profile,
            lifecycle_manager=self.lifecycle_manager,
        )

        await new_ctx.initialize()

        for comp in new_ctx.components.all_components():
            if hasattr(comp, 'component_config') and hasattr(comp.component_config, 'resolved_prompts'):
                if capability in comp.component_config.resolved_prompts:
                    old_prompt = comp.component_config.resolved_prompts[capability]
                    new_prompt = old_prompt.model_copy(
                        update={'content': prompt_content},
                        deep=False,
                    )
                    comp.component_config.resolved_prompts[capability] = new_prompt
                    comp.prompts[capability] = new_prompt

        return new_ctx

    async def clone_with_version_override(
        self,
        prompt_overrides: Optional[Dict[str, str]] = None,
        contract_overrides: Optional[Dict[str, str]] = None
    ) -> 'ApplicationContext':
        """Горячее переключение версий через клонирование."""
        from copy import deepcopy

        new_config = deepcopy(self.config)
        if prompt_overrides:
            new_config.prompt_versions.update(prompt_overrides)
        if contract_overrides:
            new_config.input_contract_versions.update(contract_overrides)
            new_config.output_contract_versions.update(contract_overrides)

        new_ctx = ApplicationContext(
            infrastructure_context=self.infrastructure_context,
            config=new_config,
            profile=self.profile
        )
        await new_ctx.initialize()
        return new_ctx

    def is_fully_initialized(self) -> bool:
        """Проверка, полностью ли инициализирована система."""
        return self.is_initialized

    async def get_all_capabilities(
        self,
        include_hidden: bool = False,
        component_types: Optional[List[str]] = None
    ) -> List['Capability']:
        """
        Получение всех доступных capability от всех навыков и инструментов.
        
        Args:
            include_hidden: включать ли скрытые capability (visiable=False)
            component_types: фильтр по типам компонентов ['skill', 'tool', 'service']
        """
        from core.errors.exceptions import ComponentInitializationError

        all_capabilities = []
        component_types = component_types or []

        if self.event_bus_logger:
            await self.event_bus_logger.debug(
                f"get_all_capabilities: Зарегистрированные компоненты: "
                f"SKILL={list(self.components._components[ComponentType.SKILL].keys())}, "
                f"TOOL={list(self.components._components[ComponentType.TOOL].keys())}"
            )

        for skill in self.components.all_of_type(ComponentType.SKILL):
            if self.event_bus_logger:
                await self.event_bus_logger.debug(
                    f"get_all_capabilities: Проверяем навык {skill.name}, "
                    f"hasattr get_capabilities={hasattr(skill, 'get_capabilities')}"
                )
            if hasattr(skill, 'get_capabilities'):
                try:
                    caps = skill.get_capabilities()
                    all_capabilities.extend(caps)
                    if self.event_bus_logger:
                        await self.event_bus_logger.debug(
                            f"get_all_capabilities: Навык {skill.name} вернул {len(caps)} capability: {[c.name for c in caps]}"
                        )
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            f"get_all_capabilities: Критическая ошибка получения capability от навыка {skill.name}: {e}"
                        )
                    raise ComponentInitializationError(
                        f"Навык {skill.name} не вернул capability: {str(e)}",
                        component=skill.name
                    )
            else:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
                        f"get_all_capabilities: Навык {skill.name} не имеет метода get_capabilities"
                    )
                raise ComponentInitializationError(
                    f"Навык {skill.name} не имеет метода get_capabilities. "
                    f"Это критическая ошибка инициализации.",
                    component=skill.name
                )

        for tool in self.components.all_of_type(ComponentType.TOOL):
            if self.event_bus_logger:
                await self.event_bus_logger.debug(
                    f"get_all_capabilities: Проверяем инструмент {tool.name}, "
                    f"hasattr get_capabilities={hasattr(tool, 'get_capabilities')}"
                )
            if hasattr(tool, 'get_capabilities'):
                try:
                    caps = tool.get_capabilities()
                    all_capabilities.extend(caps)
                    if self.event_bus_logger:
                        await self.event_bus_logger.debug(
                            f"get_all_capabilities: Инструмент {tool.name} вернул {len(caps)} capability: {[c.name for c in caps]}"
                        )
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            f"get_all_capabilities: Критическая ошибка получения capability от инструмента {tool.name}: {e}"
                        )
                    raise ComponentInitializationError(
                        f"Инструмент {tool.name} не вернул capability: {str(e)}",
                        component=tool.name
                    )
            else:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
                        f"get_all_capabilities: Инструмент {tool.name} не имеет метода get_capabilities"
                    )
                raise ComponentInitializationError(
                    f"Инструмент {tool.name} не имеет метода get_capabilities. "
                    f"Это критическая ошибка инициализации.",
                    component=tool.name
                )

        if self.event_bus_logger:
            await self.event_bus_logger.debug(
                f"get_all_capabilities: Всего получено {len(all_capabilities)} capability: {[c.name for c in all_capabilities]}"
            )
        
        filtered_caps = []
        for cap in all_capabilities:
            if not include_hidden and hasattr(cap, 'visiable') and not cap.visiable:
                continue
            if component_types:
                cap_type = getattr(cap, 'skill_name', None)
                if not cap_type or not any(ct in cap_type for ct in component_types):
                    continue
            filtered_caps.append(cap)
        
        return filtered_caps

    async def shutdown(self):
        """Корректное завершение работы ApplicationContext."""
        self.logger.info("Завершение работы ApplicationContext...")

        if self.llm_orchestrator:
            try:
                await self.llm_orchestrator.shutdown()
                self.logger.info("LLMOrchestrator завершён")
            except Exception as e:
                self.logger.error(f"Ошибка при завершении LLMOrchestrator: {e}")
            self.llm_orchestrator = None

        if self.data_repository:
            try:
                await self.data_repository.shutdown()
                self.logger.info("DataRepository завершён")
            except Exception as e:
                self.logger.error(f"Ошибка при завершении DataRepository: {e}")

        # Очистка ресурсов из LifecycleManager для возможности повторной регистрации
        if hasattr(self, 'lifecycle_manager') and self.lifecycle_manager:
            try:
                await self.lifecycle_manager.clear_resources()
                self.logger.info("LifecycleManager очищен")
            except Exception as e:
                self.logger.error(f"Ошибка при очистке LifecycleManager: {e}")

        self.logger.info("ApplicationContext завершён")
