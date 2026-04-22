"""
Прикладной контекст - версионируемый контекст для сессии/агента.

СОДЕРЖИТ:
- ComponentRegistry: сервисы, навыки, инструменты, behavior patterns
- Конфигурацию: AppConfig, флаги (side_effects_enabled, detailed_metrics)
- Ссылку на InfrastructureContext (только для чтения)

ЖИЗНЕННЫЙ ЦИКЛ:
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
"""
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal, Type

from pydantic import BaseModel

from core.components.action_executor import ActionExecutor
from core.components.component_factory import ComponentFactory
from core.application_context.base_system_context import BaseSystemContext
from core.config.component_config import ComponentConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging.event_types import LogEventType
from core.models.enums.common_enums import ComponentType, ResourceType
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

        # Логгер приложения (использует ту же сессию что и инфраструктура)
        self.log = infrastructure_context.log_session.app_logger

        data_dir = getattr(infrastructure_context.config, 'data_dir', 'data')
        self._data_dir = Path(data_dir)
        self.llm_orchestrator = None
        self._initialized = False
        self._component_factory = None  # Один factory на все компоненты

    def _get_component_factory(self) -> 'ComponentFactory':
        """Получить или создать единый ComponentFactory (синглтон на контекст)."""
        if self._component_factory is None:
            self._component_factory = ComponentFactory(self.infrastructure_context)
        return self._component_factory

    @property
    def is_ready(self) -> bool:
        """Проверка готовности контекста."""
        return self.lifecycle_manager is not None and self.lifecycle_manager.is_ready

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации контекста."""
        return self._initialized

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
        factory = self._get_component_factory()
        return factory._resolve_component_class(component_type.value, name)

    async def _create_component(self, component_type: ComponentType, name: str, config: Any, executor: 'ActionExecutor') -> 'Component':
        """ЕДИНЫЙ фабричный метод для создания ЛЮБОГО компонента."""
        factory = self._get_component_factory()
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
            self.log.warning("ApplicationContext уже инициализирован", extra={"event_type": LogEventType.WARNING})
            return True

        if not self.lifecycle_manager:
            self.lifecycle_manager = self.infrastructure_context.lifecycle_manager
        if not self.lifecycle_manager:
            raise RuntimeError("InfrastructureContext.lifecycle_manager не инициализирован")

        self.log.info(f"Начало инициализации ApplicationContext {self.id}", extra={"event_type": LogEventType.SYSTEM_INIT})

        if hasattr(self.config, 'config_id') and self.config.config_id.startswith('auto_'):
            await self._auto_fill_config()

        # Ресурсы уже загружены в InfrastructureContext
        # ResourceLoader отсканировал ФС и закэшировал все промпты/контракты
        # ComponentFactory будет брать их напрямую через resource_loader.get_component_resources()
        self.log.info(
            "Ресурсы загружены через ResourceLoader (профиль=%s)",
            self.profile,
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        executor = ActionExecutor(self)

        try:
            from core.infrastructure.providers.llm.llm_orchestrator import LLMOrchestrator
            self.log.info("Создание LLMOrchestrator...", extra={"event_type": LogEventType.SYSTEM_INIT})
            self.llm_orchestrator = LLMOrchestrator(
                event_bus=self.infrastructure_context.event_bus,
                cleanup_interval=600.0,
                max_pending_calls=100,
                log_session=self.infrastructure_context.log_session,
                executor=executor  # ✅ Передаём executor
            )
            self.log.info("Вызов llm_orchestrator.initialize()...", extra={"event_type": LogEventType.SYSTEM_INIT})
            init_success = await self.llm_orchestrator.initialize()
            if not init_success:
                from core.errors.exceptions import ComponentInitializationError
                raise ComponentInitializationError(
                    "LLMOrchestrator вернул False при инициализации. Проверьте логи.",
                    component="llm_orchestrator"
                )
            self.log.info("LLMOrchestrator инициализирован успешно!", extra={"event_type": LogEventType.SYSTEM_READY})
        except Exception as e:
            self.log.error(f"Ошибка инициализации LLMOrchestrator: {e}", exc_info=True, extra={"event_type": LogEventType.ERROR})
            from core.errors.exceptions import ComponentInitializationError
            raise ComponentInitializationError(
                f"Не удалось инициализировать LLMOrchestrator: {e}. "
                f"LLMOrchestrator критически важен для работы системы.",
                component="llm_orchestrator"
            )

        self.log.info("Начало создания компонентов...", extra={"event_type": LogEventType.SYSTEM_INIT})

        component_configs = self._resolve_component_configs()

        self.log.info(f"Конфигурации компонентов: {[(k.value, list(v.keys())) for k, v in component_configs.items() if v]}", extra={"event_type": LogEventType.SYSTEM_INIT})
        
        components_created = 0
        for comp_type, configs in component_configs.items():
            if not configs:
                continue

            self.log.info(f"Обработка типа компонента {comp_type.value}: {list(configs.keys())}", extra={"event_type": LogEventType.SYSTEM_INIT})
            for name, enriched_config in configs.items():
                self.log.info(f"Создание компонента {comp_type.value}.{name}...", extra={"event_type": LogEventType.SYSTEM_INIT})
                try:
                    component = await self._create_component(comp_type, name, enriched_config, executor)
                    self.log.info(f"Регистрация компонента {comp_type.value}.{name}...", extra={"event_type": LogEventType.SYSTEM_INIT})

                    # Регистрируем в реестре компонентов
                    self.components.register(comp_type, name, component)

                    self.log.info(f"Компонент {comp_type.value}.{name} создан и зарегистрирован", extra={"event_type": LogEventType.SYSTEM_INIT})
                    components_created += 1
                except Exception as e:
                    self.log.error(f"Ошибка создания {comp_type.value}.{name}: {e}", exc_info=True, extra={"event_type": LogEventType.ERROR})

        self.log.info(f"Создано {components_created} компонентов", extra={"event_type": LogEventType.SYSTEM_INIT})

        success = await self._initialize_components_with_dependencies()
        if not success:
            self.log.error("Ошибка инициализации компонентов с учетом зависимостей", extra={"event_type": LogEventType.ERROR})
            return False

        # РЕГИСТРАЦИЯ всех компонентов в lifecycle_manager для отображения в UI
        await self._register_components_in_lifecycle_manager()

        try:
            verify_ok = await self._verify_readiness()
        except Exception as e:
            self.log.error(f"_verify_readiness EXCEPTION: {e}", exc_info=True, extra={"event_type": LogEventType.ERROR})
            return False

        if not verify_ok:
            self.log.warning("_verify_readiness вернул False", extra={"event_type": LogEventType.WARNING})
            return False

        await self.lifecycle_manager.initialize_all()
        self._initialized = True
        self.log.info(
            f"ApplicationContext инициализирован (profile={self.profile})",
            extra={"event_type": LogEventType.USER_RESULT}
        )
        self.log.info(f"ApplicationContext {self.id} успешно инициализирован", extra={"event_type": LogEventType.SYSTEM_INIT})
        return True

    async def _initialize_components_with_dependencies(self) -> bool:
        """
        Инициализация компонентов со строгим порядком по типу:
        1. tool — инструменты (первыми, нет async зависимостей)
        2. service — сервисы (вторыми, готовы для вызовов)
        3. skill — навыки (последними, используют сервисы через executor)
        4. behavior — поведенческие паттерны (последними)

        DEPENDENCIES не используются для порядка — все вызовы через executor.
        """
        self.log.info("=== НАЧАЛО _initialize_components_with_dependencies ===", extra={"event_type": LogEventType.SYSTEM_INIT})

        all_components = self.components.all_components()
        component_map = {comp.name: comp for comp in all_components}

        # Строгий порядок инициализации по типу компонента
        type_order = [ComponentType.TOOL, ComponentType.SERVICE, ComponentType.SKILL, ComponentType.BEHAVIOR]
        initialization_order = []

        for comp_type in type_order:
            type_components = self.components.all_of_type(comp_type)
            # Сортируем по имени для детерминизма
            type_components.sort(key=lambda c: c.name)
            initialization_order.extend(c.name for c in type_components)

        initialized_components = set()
        for component_name in initialization_order:
            if component_name not in component_map:
                continue
            component = component_map[component_name]
            try:
                if hasattr(component, 'initialize') and callable(component.initialize):
                    if await component.initialize():
                        initialized_components.add(component.name)
                        self.log.info(f"Компонент инициализирован: {component.name}", extra={"event_type": LogEventType.SYSTEM_INIT})
                    else:
                        self.log.error(f"Компонент {component.name} не смог инициализироваться", extra={"event_type": LogEventType.ERROR})
                        return False
                else:
                    initialized_components.add(component.name)
                    self.log.info(f"Компонент {component.name} инициализирован (нет initialize метода)", extra={"event_type": LogEventType.SYSTEM_INIT})
            except Exception as e:
                self.log.error(f"Ошибка при инициализации компонента {component.name}: {e}", exc_info=True, extra={"event_type": LogEventType.ERROR})
                return False

        all_names = {comp.name for comp in all_components}
        if len(initialized_components) != len(all_names):
            uninitialized = all_names - initialized_components
            self.log.error(f"Не все компоненты были инициализированы: {uninitialized}", extra={"event_type": LogEventType.ERROR})
            return False

        return True

    async def _register_components_in_lifecycle_manager(self) -> None:
        """
        Регистрация всех компонентов из ComponentRegistry в lifecycle_manager.

        Это необходимо для отображения сервисов, навыков и инструментов в UI дашборде.
        Метод читает все компоненты из self.components и регистрирует их в lifecycle_manager
        с соответствующим ResourceType.
        """
        if not self.lifecycle_manager:
            self.log.warning("LifecycleManager недоступен, регистрация компонентов пропущена", extra={"event_type": LogEventType.WARNING})
            return

        # Маппинг ComponentType -> ResourceType
        type_mapping = {
            ComponentType.SERVICE: ResourceType.SERVICE,
            ComponentType.SKILL: ResourceType.SKILL,
            ComponentType.TOOL: ResourceType.TOOL,
            ComponentType.BEHAVIOR: ResourceType.BEHAVIOR,
        }

        registered_count = 0
        for comp_type in type_mapping.keys():
            components = self.components.all_of_type(comp_type)
            if not components:
                continue

            resource_type = type_mapping[comp_type]

            for component in components:
                try:
                    component_name = component.name if hasattr(component, 'name') else str(component)

                    # Собираем метаданные для UI
                    metadata = {}
                    if hasattr(component, 'description'):
                        metadata['description'] = component.description
                    if hasattr(component, 'get_capabilities'):
                        try:
                            caps = component.get_capabilities()
                            if caps:
                                metadata['capabilities'] = [c.name for c in caps]
                        except Exception:
                            pass

                    # Регистрируем в lifecycle_manager
                    await self.lifecycle_manager.register_component(
                        name=component_name,
                        component=component,
                        component_type=resource_type,
                        metadata=metadata
                    )
                    registered_count += 1

                    self.log.info(
                        f"Зарегистрирован в LifecycleManager: {comp_type.value}.{component_name}",
                        extra={"event_type": LogEventType.SYSTEM_INIT}
                    )
                except ValueError as e:
                    # Компонент уже зарегистрирован - это нормально
                    if "already registered" in str(e):
                        comp_name = component.name if hasattr(component, 'name') else 'unknown'
                        self.log.warning(
                            f"Компонент {comp_type.value}.{comp_name} уже зарегистрирован",
                            extra={"event_type": LogEventType.WARNING}
                        )
                    else:
                        comp_name = component.name if hasattr(component, 'name') else 'unknown'
                        self.log.error(
                            f"Ошибка регистрации {comp_type.value}.{comp_name}: {e}",
                            extra={"event_type": LogEventType.ERROR}
                        )
                except Exception as e:
                    comp_name = component.name if hasattr(component, 'name') else 'unknown'
                    self.log.error(
                        f"Ошибка регистрации {comp_type.value}.{comp_name}: {e}",
                        extra={"event_type": LogEventType.ERROR}
                    )

        self.log.info(
            f"В LifecycleManager зарегистрировано {registered_count} компонентов",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

    async def _verify_readiness(self) -> bool:
        """Валидация, что ВСЕ компоненты готовы к работе."""
        declared_components = self._resolve_component_configs()
        for comp_type, names in declared_components.items():
            for name in names:
                component = self.components.get(comp_type, name)
                if component is None:
                    self.log.error(f"Компонент {comp_type.value}.{name} не найден", extra={"event_type": LogEventType.ERROR})
                    return False
                if hasattr(component, 'is_initialized') and callable(component.is_initialized):
                    if not component.is_initialized():
                        self.log.error(f"Компонент {comp_type.value}.{name} не инициализирован", extra={"event_type": LogEventType.ERROR})
                        return False
                elif hasattr(component, '_initialized'):
                    if not component._initialized:
                        self.log.error(f"Компонент {comp_type.value}.{name} не инициализирован", extra={"event_type": LogEventType.ERROR})
                        return False
                elif hasattr(component, 'is_ready') and callable(component.is_ready):
                    if not component.is_ready():
                        self.log.error(f"Компонент {component.name} не готов к работе", extra={"event_type": LogEventType.ERROR})
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
        self.log.info(
            f"Health check: {health_report['overall_status']}, "
            f"{health_report['metrics']['healthy_components']}/{health_report['metrics']['total_components']} healthy",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )
        return health_report

    def get_behavior_pattern(self, name: str) -> Optional['Component']:
        return self.components.get(ComponentType.BEHAVIOR, name)

    def get_service(self, name: str) -> Optional[Any]:
        """Получение сервиса по имени."""
        return self.components.get(ComponentType.SERVICE, name)

    async def _validate_versions_by_profile(self, prompt_versions: dict, input_contract_versions: dict = None, output_contract_versions: dict = None) -> bool:
        """Валидация версий в зависимости от профиля и prompt_loading_config.

        Ресурсы уже загружены и валидированы в ResourceLoader.
        Проверяем только наличие запрошенных версий.
        """
        from core.errors.exceptions import ComponentInitializationError

        loader = self.infrastructure_context.resource_loader
        if not loader:
            raise ComponentInitializationError("ResourceLoader не инициализирован")

        if prompt_versions:
            for capability, version in prompt_versions.items():
                prompt = loader.get_prompt(capability, version)
                if not prompt:
                    raise ComponentInitializationError(
                        f"Промпт {capability}@{version} не найден в ResourceLoader"
                    )

                # Проверка статуса для prod
                if self.profile == "prod" and prompt.status.value != "active":
                    raise ComponentInitializationError(
                        f"[PROD] Промпт {capability}@{version} имеет статус '{prompt.status.value}', "
                        f"но требуется 'active'."
                    )

        if input_contract_versions:
            for capability, version in input_contract_versions.items():
                contract = loader.get_contract(capability, version, "input")
                if not contract:
                    raise ComponentInitializationError(
                        f"Входной контракт {capability}@{version} не найден в ResourceLoader"
                    )

        if output_contract_versions:
            for capability, version in output_contract_versions.items():
                contract = loader.get_contract(capability, version, "output")
                if not contract:
                    raise ComponentInitializationError(
                        f"Выходной контракт {capability}@{version} не найден в ResourceLoader"
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
        self.config = type(self.config).from_discovery(
            profile=self.profile,
            data_dir=str(self._data_dir),
        )

    def get_prompt(self, capability: str, version: Optional[str] = None) -> str:
        """Получение текста промпта через ResourceLoader."""
        content_overrides = getattr(self.config, '_prompt_content_overrides', {})
        if capability in content_overrides:
            return content_overrides[capability]

        loader = self.infrastructure_context.resource_loader
        if loader:
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
                        self.log.warning(
                            f"Промпт '{capability}' не найден в конфигурации (версия не указана). "
                            f"Возвращаем пустую строку.",
                            extra={"event_type": LogEventType.WARNING}
                        )
                        return ""

            if version:
                try:
                    prompt_obj = loader.get_prompt(capability, version)
                    if prompt_obj:
                        return prompt_obj.content
                except Exception as e:
                    self.log.error(
                        f"Ошибка получения промпта '{capability}@{version}': {e}. "
                        f"Возвращаем пустую строку.",
                        extra={"event_type": LogEventType.ERROR}
                    )
        return ""

    def get_input_contract_schema(self, capability: str, version: Optional[str] = None) -> Type[BaseModel]:
        """Возвращает скомпилированную схему для валидации входных данных."""
        loader = self.infrastructure_context.resource_loader
        if loader:
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
                    contract = loader.get_contract(capability, version, "input")
                    if contract:
                        return contract.pydantic_schema
                except Exception:
                    pass
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

    async def set_prompt_override(self, capability: str, version: str):
        """Установка оверрайда версии промпта (только для песочницы)."""
        if self.profile != "sandbox":
            raise RuntimeError("Оверрайды версий разрешены ТОЛЬКО в режиме песочницы")

        prompt_path = self._data_dir / "prompts" / capability / f"{version}.yaml"
        if not prompt_path.exists():
            prompt_path_json = self._data_dir / "prompts" / capability / f"{version}.json"
            if not prompt_path_json.exists():
                raise ValueError(f"Версия {capability}@{version} не существует")

        self._prompt_overrides[capability] = version
        self.log.info(f"Установлен оверрайд: {capability}@{version} для песочницы", extra={"event_type": LogEventType.SYSTEM_INIT})

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
        - capability: имя capability (например 'planning.create_plan')
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
            component_types: фильтр по типам компонентов ['skill', 'tool']
        """
        from core.errors.exceptions import ComponentInitializationError
        from core.models.data.capability import Capability
        
        def collect_capabilities(component, comp_type: str) -> List[Capability]:
            """Сбор capability от одного компонента."""
            if not hasattr(component, 'get_capabilities'):
                raise ComponentInitializationError(
                    f"Компонент {component.name} не имеет метода get_capabilities",
                    component=component.name
                )
            try:
                caps = component.get_capabilities()
                result_caps = []
                for cap in caps:
                    cap_dict = cap.model_dump()
                    cap_dict['component_type'] = comp_type
                    result_caps.append(Capability(**cap_dict))
                return result_caps
            except Exception as e:
                raise ComponentInitializationError(
                    f"Ошибка получения capability от {comp_type} {component.name}: {e}",
                    component=component.name
                )
        
        def should_include(cap: Capability) -> bool:
            """Проверка включения capability в результат."""
            if not include_hidden and hasattr(cap, 'visiable') and not cap.visiable:
                return False
            if not component_types:
                return True
            cap_type = getattr(cap, 'component_type', None) or getattr(cap, 'skill_name', '')
            for ct in component_types:
                if ct == "skill" and not cap_type.endswith("_tool"):
                    return True
                if ct == "tool" and cap_type.endswith("_tool"):
                    return True
            return False
        
        all_capabilities = []
        component_types = component_types or []
        
        for comp_type in [ComponentType.SKILL, ComponentType.TOOL]:
            for comp in self.components.all_of_type(comp_type):
                caps = collect_capabilities(comp, comp_type.value)
                all_capabilities.extend(caps)
        
        return [cap for cap in all_capabilities if should_include(cap)]

    async def shutdown(self):
        """Корректное завершение работы ApplicationContext."""
        self.log.info("Завершение работы ApplicationContext...", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})

        if self.llm_orchestrator:
            try:
                await self.llm_orchestrator.shutdown()
                self.log.info("LLMOrchestrator завершён", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
            except Exception as e:
                self.log.error(f"Ошибка при завершении LLMOrchestrator: {e}", extra={"event_type": LogEventType.ERROR})
            self.llm_orchestrator = None

        # DataRepository удалён, ресурсы в ResourceLoader
        # ResourceLoader не требует shutdown — только кэш в памяти

        # Очистка ресурсов из LifecycleManager для возможности повторной регистрации
        if hasattr(self, 'lifecycle_manager') and self.lifecycle_manager:
            try:
                await self.lifecycle_manager.clear_resources()
                self.log.info("LifecycleManager очищен", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
            except Exception as e:
                self.log.error(f"Ошибка при очистке LifecycleManager: {e}", extra={"event_type": LogEventType.ERROR})

        self.log.info("ApplicationContext завершён", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
