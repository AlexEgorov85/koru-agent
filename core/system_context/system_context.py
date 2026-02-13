"""
Системный контекст - адаптер для новой архитектуры с разделением на InfrastructureContext и ApplicationContext.
ОСОБЕННОСТИ:
- Обратная совместимость с существующим кодом
- Использование новой архитектуры с изолированными контекстами
- Постепенная миграция к новой архитектуре
"""
import uuid
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from core.agent_runtime.runtime import AgentRuntime
from core.config.models import SystemConfig
from core.config.component_config import ComponentConfig
from core.session.base_session_context import BaseSessionContext
from core.session_context.session_context import SessionContext
from core.application.context.application_context import ApplicationContext
from core.system_context.execution_gateway import ExecutionGateway
from core.system_context.resource_registry import ResourceRegistry, ResourceInfo
from core.system_context.capability_registry import CapabilityRegistry
from core.system_context.lifecycle_manager import LifecycleManager

from core.infrastructure.providers.factory import ProviderFactory
from models.capability import Capability
from models.llm_types import LLMRequest, LLMResponse, RawLLMResponse, StructuredLLMResponse, StructuredOutputConfig
from models.resource import ResourceType, ResourceHealth
from core.errors.structured_output import StructuredOutputError
from pydantic import ValidationError
from pydantic.main import BaseModel as PydanticBaseModel
import json

# Импорты для инфраструктурных сервисов
from core.application.services.base_service import BaseService
from core.application.services.prompt_service import PromptService
from core.application.services.sql_generation.service import SQLGenerationService
from core.application.services.sql_query.service import SQLQueryService
from core.application.services.sql_validator.service import SQLValidatorService
from core.system_context.dependency_resolver import DependencyResolver, ServiceDescriptor
from core.errors.architecture_violation import CircularDependencyError
from typing import Type, Dict

# Импорты для шины событий
from core.infrastructure.event_bus.event_bus import EventBus, EventType, get_event_bus, Event
from core.infrastructure.event_bus.event_handlers import MetricsEventHandler, AuditEventHandler

# Импорты для новой архитектуры
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.infrastructure.context.agent_factory import AgentFactory, ProfileType

logger = logging.getLogger(__name__)

class SystemContext(BaseSystemContext):
    """
    Cистемный контекст - центральный фасад системы.

    АРХИТЕКТУРА:
    - Pattern: Facade
    - Инкапсулирует сложность внутренних подсистем
    - Предоставляет единую точку доступа ко всей системе

    ВНУТРЕННИЕ КОМПОНЕНТЫ:
    - registry: Реестр ресурсов
    - capabilities: Реестр capability
    - lifecycle: Менеджер жизненного цикла
    - config: Конфигурация
    - agents: Фабрика агентов
    - provider_factory: Фабрика провайдеров

    ИНИЦИАЛИЗАЦИЯ:
    1. Создание всех компонентов
    2. Регистрация стандартных ресурсов
    3. Инициализация через lifecycle manager
    """

    def __init__(self, config: Optional[SystemConfig] = None):
        """
        Инициализация системного контекста как адаптера к новой архитектуре.

        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (опционально)

        СОЗДАВАЕМЫЕ КОМПОНЕНТЫ:
        - infrastructure_context: Инфраструктурный контекст (общие ресурсы)
        - application_context: Прикладной контекст (изолированные кэши)
        - agent_factory: Фабрика агентов с изоляцией
        - config: Конфигурация
        - event_bus: Шина событий

        ОСОБЕННОСТИ:
        - Создает инфраструктурный контекст (один на всё приложение)
        - Создает прикладной контекст по умолчанию (для обратной совместимости)
        - Обеспечивает совместимость с существующим API
        """
        self.id = str(uuid.uuid4())
        self.config = config or SystemConfig()
        
        # Создаем инфраструктурный контекст (один на всё приложение)
        self.infrastructure_context = InfrastructureContext(self.config)
        
        # Создаем прикладной контекст по умолчанию (для обратной совместимости)
        from core.config.models import AgentConfig
        default_agent_config = AgentConfig(
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False
        )
        self.application_context = ApplicationContext(
            infrastructure=self.infrastructure_context,
            config=default_agent_config
        )
        
        # Фабрика агентов для создания изолированных агентов
        self.agent_factory = AgentFactory(self.infrastructure_context)
        
        # Для обратной совместимости - сохраняем старые атрибуты
        self.registry = ResourceRegistry()  # ← Теперь управляет и ресурсами, и capability
        self.lifecycle = LifecycleManager(self.registry)  # ← Передаём ЕДИНЫЙ реестр
        self.initialized = False
        self.execution_gateway = ExecutionGateway(system_context=self)

        # Инициализация фабрики провайдеров (для обратной совместимости)
        self.provider_factory = ProviderFactory(self.infrastructure_context)

        # Инициализация реестра инфраструктурных сервисов
        self.service_registry = {}

        # Инициализация шины событий
        self.event_bus = get_event_bus()
        self._setup_event_handlers()

        # Настройка логирования (временно для совместимости)
        self._setup_logging()
        # Создаем атрибут logger для совместимости с компонентами
        self.logger = logging.getLogger(__name__)

    @property
    def capabilities(self):
        """
        BACKWARD COMPATIBILITY PROPERTY: Provides access to the capability registry
        through the unified registry. This maintains the old interface while using
        the new unified architecture.
        """
        # Return the internal capability registry from the unified ResourceRegistry
        return self.registry._capabilities

    def _setup_event_handlers(self):
        """
        Настройка обработчиков событий для замены логирования.

        ОСОБЕННОСТИ:
        - Регистрация обработчиков событий
        - Настройка директорий для логов событий
        - Подписка на нужные типы событий
        """
        # Создание обработчиков событий
        self.metrics_handler = MetricsEventHandler()
        self.audit_handler = AuditEventHandler(
            audit_log_dir=os.path.join(self.config.log_dir or "logs", "audit")
        )

        # Подписка обработчиков на события
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self.metrics_handler.handle_event)

        # Подписка AuditEventHandler только на аудит-события
        from core.infrastructure.event_bus.event_handlers import AUDIT_EVENTS
        for event_type in AUDIT_EVENTS:
            self.event_bus.subscribe(event_type, self.audit_handler.handle_event)

        # Также подписываемся на все события для общего обработчика
        self.event_bus.subscribe_all(lambda event: self._handle_system_event(event))

    def _handle_system_event(self, event: Event):
        """
        Общий обработчик системных событий.

        ARGS:
        - event: событие для обработки
        """
        # Здесь можно добавить общую логику обработки событий
        pass

    def _setup_logging(self):
        """
        Настройка логирования на основе конфигурации.

        ОСОБЕННОСТИ:
        - Установка уровня логирования
        - Настройка форматирования
        - Добавление обработчиков
        """
        # Создание директории для логов если не существует
        log_dir = self.config.log_dir or "logs"
        os.makedirs(log_dir, exist_ok=True)

        # Установка уровня логирования
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(level=log_level, encoding='utf-8')


        # Создание обработчика для файла
        log_file = os.path.join(log_dir, f"system_{self.id[:8]}.log")
        file_handler = logging.FileHandler(
            filename=log_file,
            encoding='utf-8',
            mode='a'
            )

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(file_handler)


    async def initialize(self) -> bool:
        """Инициализация системного контекста с использованием новой архитектуры."""
        import time
        start_time = time.time()

        self.logger.info("=== Начало инициализации системы (новая архитектура) ===")

        # Инициализация инфраструктурного контекста (один на всё приложение)
        await self.infrastructure_context.initialize()
        
        # Инициализация прикладного контекста по умолчанию (для обратной совместимости)
        await self.application_context.initialize()

        # Для обратной совместимости - также выполняем старую инициализацию
        # Регистрация провайдеров из конфигурации до построения графа зависимостей
        self.logger.info("Регистрация провайдеров из конфигурации...")
        await self._register_providers_from_config()

        # === ФАЗА 1: Построение графа зависимостей (регистрация дескрипторов + топосорт за один проход) ===
        self.logger.info("ФАЗА 1: Построение графа зависимостей...")
        init_order = await self._build_init_graph()
        self.logger.info(f"Порядок инициализации: {' → '.join(init_order)}")

        # === ФАЗА 2: Параллельная инициализация сервисов ===
        self.logger.info("ФАЗА 2: Параллельная инициализация сервисов...")
        if not await self._atomic_init(init_order):
            return False

        self.initialized = True
        end_time = time.time()
        duration = end_time - start_time
        self.logger.info(f"=== Система успешно инициализирована за {duration:.2f} секунд ===")

        # Отправляем метрику времени инициализации
        from core.infrastructure.event_bus.event_bus import EventType
        await self.event_bus.publish(
            EventType.METRIC_COLLECTED,
            data={
                "metric_name": "system.initialization_time",
                "value": duration,
                "unit": "seconds",
                "system_id": self.id
            },
            source="SystemContext.initialize",
            correlation_id=self.id
        )

        return True

    async def _build_init_graph(self) -> list:
        """Построение графа зависимостей: регистрация дескрипторов + топосорт за один проход."""
        # 1. Обнаружение дескрипторов сервисов
        service_descriptors = await self._discover_service_descriptors()

        # Валидация дескрипторов
        if not await self._validate_service_descriptors(service_descriptors):
            return []

        # Сохранение дескрипторов для последующих операций
        self._service_descriptors = service_descriptors

        # 2. Расчет порядка инициализации (топологическая сортировка)
        try:
            init_order = await DependencyResolver.calculate_initialization_order(service_descriptors)
        except CircularDependencyError as e:
            self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
            await self._dump_dependency_graph(service_descriptors)
            return []

        return init_order

    async def _atomic_init(self, init_order: list) -> bool:
        """Атомарная инициализация сервисов с предзагрузкой ресурсов."""
        # Инициализация сервисов в заданном порядке
        for service_name in init_order:
            if not await self._instantiate_and_initialize_service(service_name, self._service_descriptors):
                self.logger.error(f"Не удалось инициализировать сервис '{service_name}'")
                return False

        # Создание и регистрация навыков на основе конфигурации
        try:
            await self.provider_factory.discover_and_create_all_skills()
            self.logger.info("Навыки успешно обнаружены и зарегистрированы")
        except Exception as e:
            self.logger.error(f"Ошибка при создании навыков: {str(e)}")
            # Не прерываем инициализацию, если навыки не удалось создать, т.к. это не критично

        # Создание и регистрация инструментов на основе конфигурации
        try:
            await self.provider_factory.discover_and_create_all_tools()
            
            # Логирование зарегистрированных инструментов для отладки
            registered_tools = self.registry.get_resources_by_type(ResourceType.TOOL)
            tool_names = [resource.name for resource in registered_tools]
            self.logger.info(f"Инструменты успешно обнаружены и зарегистрированы: {tool_names}")
        except Exception as e:
            self.logger.error(f"Ошибка при создании инструментов: {str(e)}")
            # Не прерываем инициализацию, если инструменты не удалось создать, т.к. это не критично

        # Предзагрузка ресурсов (встроена в инициализацию, как указано в требованиях)
        if not await self._preload_system_resources():
            return False

        # Проверка готовности (заменяет финальную верификацию)
        if not await self._verify_system_readiness():
            return False

        return True

    async def _discover_service_descriptors(self) -> Dict[str, ServiceDescriptor]:
        """Обнаружение и регистрация дескрипторов сервисов (без создания экземпляров!)."""
        descriptors = {}

        # 1. Критические сервисы (регистрируем вручную для контроля порядка)
        critical_services = {
            "prompt_service": PromptService,
        }

        # Импортируем и добавляем другие критические сервисы
        try:
            from core.application.services.contract_service import ContractService
            critical_services["contract_service"] = ContractService
        except ImportError:
            self.logger.warning("ContractService не найден")

        try:
            from core.application.services.table_description_service import TableDescriptionService
            critical_services["table_description_service"] = TableDescriptionService
        except ImportError:
            self.logger.warning("TableDescriptionService не найден")

        for name, cls in critical_services.items():
            if cls is not None:
                descriptors[name] = ServiceDescriptor(name=name, service_class=cls)

        # 2. Автоматическое обнаружение остальных сервисов
        discovered = await self.provider_factory._discover_services_from_directory()
        for name, cls in discovered.items():
            if name not in descriptors:  # Не перезаписываем критические
                # Пропускаем отключённые в конфигурации
                if not self._is_service_enabled(name):
                    self.logger.debug(f"Сервис '{name}' отключён в конфигурации — пропускаем")
                    continue
                descriptors[name] = ServiceDescriptor(name=name, service_class=cls)

        return descriptors

    async def _instantiate_and_initialize_service(
        self,
        service_name: str,
        descriptors: Dict[str, ServiceDescriptor]
    ) -> bool:
        """Создание экземпляра сервиса и его инициализация."""
        descriptor = descriptors[service_name]

        # 1. Создание экземпляра
        try:
            service = await self._create_service_instance(service_name, descriptor.service_class)
        except Exception as e:
            self.logger.exception(f"Ошибка создания экземпляра '{service_name}': {e}")
            return False

        # 2. Создание ResourceInfo с PENDING статусом
        resource_info = ResourceInfo(
            name=service_name,
            resource_type=ResourceType.SERVICE,
            instance=service
        )
        # Добавляем метаданные как атрибут
        resource_info.metadata = {"class": descriptor.service_class.__name__}
        resource_info.health = ResourceHealth.PENDING  # Устанавливаем статус PENDING
        
        # 3. Регистрация в реестре с PENDING статусом (чтобы зависимости могли его найти, но не использовать)
        self.registry.register_resource(resource_info)

        # 4. Инициализация
        self.logger.debug(f"Инициализация сервиса '{service_name}'...")
        if not await service.initialize():
            self.logger.error(f"Сервис '{service_name}' не прошёл инициализацию")
            # Отмена регистрации при ошибке
            try:
                self.registry.unregister_resource(service_name)
            except KeyError:
                pass  # Ресурс уже мог быть удален
            return False

        # 5. Обновление статуса на READY после успешной инициализации
        resource_info.health = ResourceHealth.HEALTHY
        self.logger.info(f"✓ Сервис '{service_name}' успешно инициализирован и зарегистрирован (статус=HEALTHY)")
        return True

    async def _create_service_instance(self, name: str, service_class: Type[BaseService]) -> BaseService:
        """Создание экземпляра сервиса с правильной конфигурацией."""
        # Получение конфигурации из системной конфигурации
        service_config = self._get_service_config(name)
        
        # Создание ComponentConfig
        component_config = ComponentConfig(
            variant_id=service_config.get("variant_id", f"{name}_default"),
            prompt_versions=service_config.get("prompt_versions", {}),
            input_contract_versions=service_config.get("input_contract_versions", {}),
            output_contract_versions=service_config.get("output_contract_versions", {})
        )
        
        # Создание экземпляра
        return service_class(
            system_context=self,
            name=name,
            component_config=component_config
        )

    async def _preload_system_resources(self) -> bool:
        """Предзагрузка всех промптов и контрактов после инициализации сервисов."""
        prompt_service = await self.get_service("prompt_service")
        contract_service = await self.get_service("contract_service")
        
        if not prompt_service or not contract_service:
            self.logger.error("Не найдены критические сервисы для предзагрузки ресурсов")
            return False
        
        # Предзагрузка через системную конфигурацию агента
        agent_config = getattr(self.config, 'agent_config', None)
        if not agent_config:
            self.logger.warning("agent_config не найден в системной конфигурации — пропускаем предзагрузку")
            return True
        
        # Предзагрузка промптов
        await prompt_service.preload_prompts(agent_config)
        self.registry.mark_prompts_as_preloaded()
        
        # Предзагрузка контрактов
        await contract_service.preload_contracts(agent_config)
        self.registry.mark_contracts_as_preloaded()
        
        self.logger.info("Все промпты и контракты предзагружены")
        return True

    async def _verify_system_readiness(self) -> bool:
        """Финальная проверка готовности системы."""
        # 1. Проверка всех сервисов
        all_services = self._get_resources_by_type(ResourceType.SERVICE)
        uninitialized = [
            name for name, info in all_services.items()
            if not getattr(info.instance, '_initialized', False)
        ]
        
        if uninitialized:
            self.logger.error(f"Неинициализированные сервисы: {uninitialized}")
            return False
        
        # 2. Проверка предзагрузки ресурсов
        # Проверяем, была ли попытка предзагрузки
        # Если agent_config не найден, предзагрузка может быть пропущена, и это нормально
        agent_config_exists = hasattr(self.config, 'agent_config') and self.config.agent_config is not None
        
        if agent_config_exists:
            if not self.registry.are_prompts_preloaded():
                self.logger.error("Промпты не предзагружены")
                return False

            if not self.registry.are_contracts_preloaded():
                self.logger.error("Контракты не предзагружены")
                return False
        
        # 3. Проверка критических сервисов
        critical = ["prompt_service", "contract_service", "table_description_service"]
        for name in critical:
            if not await self.get_service(name):
                self.logger.error(f"Критический сервис '{name}' недоступен")
                return False
        
    async def _validate_version_consistency(self) -> List[str]:
        """
        Проверяет:
        - Все указанные в ComponentConfig версии существуют
        - Промпт и контракт для одной capability семантически совместимы
        - Нет "висячих" зависимостей (например, инструмент зависит от незарегистрированного БД-провайдера)
        """
        errors = []
        
        # Проверяем все компоненты с ComponentConfig
        for name, info in self.registry._resources.items():
            if hasattr(info.instance, 'component_config') and info.instance.component_config:
                config = info.instance.component_config
                
                # Проверяем существование версий промптов
                for capability, version in config.prompt_versions.items():
                    prompt_service = await self.get_service("prompt_service")
                    if prompt_service and hasattr(prompt_service, 'check_version_exists'):
                        try:
                            # Проверяем, что промпт с такой версией существует
                            prompt_exists = await prompt_service.check_version_exists(capability, version)
                            if not prompt_exists:
                                errors.append(f"Промпт для capability '{capability}' версии '{version}' не существует (компонент: {name})")
                        except Exception as e:
                            errors.append(f"Ошибка проверки существования промпта '{capability}' версии '{version}': {str(e)} (компонент: {name})")
                
                # Проверяем существование версий входных контрактов
                for capability, version in config.input_contract_versions.items():
                    contract_service = await self.get_service("contract_service")
                    if contract_service and hasattr(contract_service, 'check_version_exists'):
                        try:
                            # Проверяем, что контракт с такой версией существует
                            contract_exists = await contract_service.check_version_exists(capability, version, "input")
                            if not contract_exists:
                                errors.append(f"Входной контракт для capability '{capability}' версии '{version}' не существует (компонент: {name})")
                        except Exception as e:
                            errors.append(f"Ошибка проверки существования входного контракта '{capability}' версии '{version}': {str(e)} (компонент: {name})")
                
                # Проверяем существование версий выходных контрактов
                for capability, version in config.output_contract_versions.items():
                    contract_service = await self.get_service("contract_service")
                    if contract_service and hasattr(contract_service, 'check_version_exists'):
                        try:
                            # Проверяем, что контракт с такой версии существует
                            contract_exists = await contract_service.check_version_exists(capability, version, "output")
                            if not contract_exists:
                                errors.append(f"Выходной контракт для capability '{capability}' версии '{version}' не существует (компонент: {name})")
                        except Exception as e:
                            errors.append(f"Ошибка проверки существования выходного контракта '{capability}' версии '{version}': {str(e)} (компонент: {name})")
        
        return errors

    async def _verify_system_readiness(self) -> bool:
        """Финальная проверка готовности системы."""
        # 1. Проверка согласованности версий
        version_errors = await self._validate_version_consistency()
        if version_errors:
            for error in version_errors:
                self.logger.error(error)
            return False

        # 2. Проверка всех сервисов
        all_services = self._get_resources_by_type(ResourceType.SERVICE)
        uninitialized = [
            name for name, info in all_services.items()
            if not getattr(info.instance, '_initialized', False)
        ]

        if uninitialized:
            self.logger.error(f"Неинициализированные сервисы: {uninitialized}")
            return False

        # 3. Проверка предзагрузки ресурсов
        # Проверяем, была ли попытка предзагрузки
        # Если agent_config не найден, предзагрузка может быть пропущена, и это нормально
        agent_config_exists = hasattr(self.config, 'agent_config') and self.config.agent_config is not None

        if agent_config_exists:
            if not self.registry.are_prompts_preloaded():
                self.logger.error("Промпты не предзагружены")
                return False

            if not self.registry.are_contracts_preloaded():
                self.logger.error("Контракты не предзагружены")
                return False

        # 4. Проверка критических сервисов
        critical = ["prompt_service", "contract_service", "table_description_service"]
        for name in critical:
            if not await self.get_service(name):
                self.logger.error(f"Критический сервис '{name}' недоступен")
                return False

        self.logger.info("✓ Система полностью готова к работе")
        return True

    async def _dump_dependency_graph(self, descriptors: Dict[str, ServiceDescriptor]):
        """Дамп графа зависимостей для диагностики."""
        self.logger.info("=== Граф зависимостей ===")
        for name, descriptor in descriptors.items():
            deps = getattr(descriptor.service_class, 'DEPENDENCIES', [])
            status = "✓" if deps else "•"
            self.logger.info(f"{status} {name}: {deps or 'нет зависимостей'}")

    async def _validate_service_descriptors(self, descriptors: Dict[str, ServiceDescriptor]) -> bool:
        """Валидация дескрипторов сервисов."""
        # Проверим, что все зависимости существуют
        all_service_names = set(descriptors.keys())
        for name, descriptor in descriptors.items():
            deps = getattr(descriptor.service_class, 'DEPENDENCIES', [])
            missing_deps = [dep for dep in deps if dep not in all_service_names]
            if missing_deps:
                self.logger.error(f"Сервис '{name}' имеет несуществующие зависимости: {missing_deps}")
                return False
        return True

    def _is_service_enabled(self, service_name: str) -> bool:
        """Проверка, включен ли сервис в конфигурации."""
        # Пока возвращаем True, но в будущем можно добавить логику из конфигурации
        return True

    def _get_service_config(self, service_name: str) -> Dict[str, Any]:
        """Получение конфигурации сервиса из системной конфигурации."""
        # Возвращаем пустую конфигурацию по умолчанию
        return {
            "variant_id": f"{service_name}_default",
            "prompt_versions": {},
            "input_contract_versions": {},
            "output_contract_versions": {}
        }

    async def _verify_components_use_modern_config(self):
        """Гарантия архитектуры: проверка, что компоненты, которые должны использовать ComponentConfig, его используют"""
        # Проверяем только компоненты, которые должны использовать ComponentConfig (навыки, инструменты, сервисы)
        # Провайдеры и другие системные компоненты могут не использовать эту архитектуру
        errors = []
        for name, info in self.registry._resources.items():
            # Проверяем только навыки, инструменты и сервисы
            if info.resource_type in [ResourceType.SKILL, ResourceType.TOOL, ResourceType.SERVICE]:
                if hasattr(info.instance, 'component_config') and info.instance.component_config:
                    # Компонент использует ComponentConfig - это хорошо
                    continue
                elif hasattr(info.instance, 'component_config'):
                    # Компонент имеет атрибут component_config, но он пустой или None
                    errors.append(f"Компонент '{name}' имеет атрибут component_config, но он не инициализирован")
                else:
                    # Компонент не имеет атрибута component_config вообще
                    errors.append(f"Компонент '{name}' не использует ComponentConfig (legacy-режим)")

        if errors:
            from core.errors.architecture_violation import ArchitectureViolationError
            raise ArchitectureViolationError("\n".join(errors))

    async def _verify_all_components_initialized(self):
        """Финальная проверка: все компоненты инициализированы"""
        uninitialized_components = []
        for name, info in self.registry._resources.items():
            # Проверяем, что компонент инициализирован (у него есть изолированные кэши)
            if hasattr(info.instance, '_cached_prompts') and hasattr(info.instance, '_cached_input_contracts') and hasattr(info.instance, '_cached_output_contracts'):
                # Проверяем, что кэши не пусты (или что компонент прошел инициализацию)
                # Проверяем наличие атрибута _is_initialized и его значение
                is_initialized = getattr(info.instance, '_is_initialized', False)
                if not is_initialized:
                    uninitialized_components.append(f"Компонент '{name}' не прошел полную инициализацию")
            else:
                # Компонент не имеет необходимых атрибутов, значит, не наследуется от BaseComponent
                # Но это может быть нормально для некоторых компонентов (например, провайдеров)
                # Поэтому не будем считать это ошибкой архитектуры
                pass

        if uninitialized_components:
            from core.errors.architecture_violation import ArchitectureViolationError
            raise ArchitectureViolationError("\n".join(uninitialized_components))

    def is_fully_initialized(self) -> bool:
        """
        Проверка, полностью ли инициализирована система (все ресурсы предзагружены и сервисы инициализированы).

        RETURNS:
        - bool: True если система полностью готова к работе
        """
        if not self.initialized:
            return False

        # Проверяем статус предзагрузки через реестр
        preload_status = self.registry.verify_all_resources_preloaded()

        # Проверяем, что все сервисы инициализированы
        all_services = self._get_resources_by_type(ResourceType.SERVICE)
        uninitialized_services = [
            name for name, info in all_services.items()
            if not getattr(info.instance, '_initialized', False)
        ]

        # Проверяем, была ли попытка предзагрузки
        # Если agent_config не найден, предзагрузка может быть пропущена, и это нормально
        agent_config_exists = hasattr(self.config, 'agent_config') and self.config.agent_config is not None

        # Для новой архитектуры проверяем, что все критические компоненты загружены
        # Но не требуем, чтобы все компоненты использовали новую архитектуру
        required_checks = [
            preload_status.get("resources_loaded", True),  # по умолчанию True
            # Если agent_config существует, проверяем, что промпты предзагружены, иначе пропускаем проверку
            preload_status.get("prompts_preloaded", True) if agent_config_exists else True,
            # Если agent_config существует, проверяем, что контракты предзагружены, иначе пропускаем проверку
            preload_status.get("contracts_preloaded", True) if agent_config_exists else True,
            len(uninitialized_services) == 0  # все сервисы должны быть инициализированы
        ]

        return all(required_checks)

    async def _initialize_services_with_caching(self, system_resources_config):
        """Инициализация сервисов с кэшированием промптов и контрактов."""
        # В новой архитектуре инициализация происходит через ComponentConfig
        # Этот метод больше не используется, так как каждый компонент инициализируется через BaseComponent
        pass

    async def _initialize_tools_with_caching(self, system_resources_config):
        """Инициализация инструментов с кэшированием промптов и контрактов."""
        # В новой архитектуре инициализация происходит через ComponentConfig
        # Этот метод больше не используется, так как каждый компонент инициализируется через BaseComponent
        pass

    async def _initialize_skills_with_caching(self, system_resources_config):
        """Инициализация навыков с кэшированием промптов и контрактов."""
        # В новой архитектуре инициализация происходит через ComponentConfig
        # Этот метод больше не используется, так как каждый компонент инициализируется через BaseComponent
        pass
        
    async def shutdown(self) -> None:
        """
        Завершение работы системы.

        ПРОЦЕСС:
        1. Корректное завершение работы всех ресурсов
        2. Завершение работы инфраструктурных сервисов
        3. Установка флага initialized в False
        4. Публикация события завершения работы

        ОСОБЕННОСТИ:
        - Метод безопасен для повторного вызова
        - Ошибки при завершении отдельных ресурсов не прерывают процесс
        - Все ресурсы получают шанс корректно завершить работу
        """
        if not self.initialized:
            return

        # Публикация события начала завершения работы
        await self.event_bus.publish(
            EventType.SYSTEM_SHUTDOWN,
            data={"system_id": self.id, "reason": "normal_shutdown"},
            source="SystemContext.shutdown",
            correlation_id=self.id
        )

        # Завершение работы инфраструктурных сервисов
        await self._shutdown_infrastructure_services()

        await self.lifecycle.shutdown()
        self.initialized = False
        
        # Публикация события завершения работы
        await self.event_bus.publish(
            EventType.SYSTEM_SHUTDOWN,
            data={"system_id": self.id, "status": "completed"},
            source="SystemContext.shutdown_complete",
            correlation_id=self.id
        )

    async def register_service(self, service_name: str, service: BaseService) -> bool:
        """
        Регистрация инфраструктурного сервиса.

        ARGS:
        - service_name: имя сервиса
        - service: экземпляр сервиса

        RETURNS:
        - True если регистрация прошла успешно, иначе False
        """
        try:
            # Проверка, что сервис наследуется от BaseService
            if not isinstance(service, BaseService):
                raise TypeError(f"Service must inherit from BaseService, got {type(service)}")

            # Регистрация сервиса в реестре
            self.service_registry[service_name] = service

            # Публикация события регистрации сервиса
            await self.event_bus.publish(
                EventType.SERVICE_REGISTERED,
                data={
                    "service_name": service_name,
                    "service_type": type(service).__name__,
                    "system_id": self.id
                },
                source="SystemContext.register_service",
                correlation_id=self.id
            )

            return True
        except Exception as e:
            # Публикация события ошибки регистрации сервиса
            await self.event_bus.publish(
                EventType.SYSTEM_ERROR,
                data={
                    "service_name": service_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "system_id": self.id
                },
                source="SystemContext.register_service",
                correlation_id=self.id
            )
            return False

    async def get_service(self, service_name: str, timeout: float = 5.0) -> Optional[BaseService]:
        """
        Получение инфраструктурного сервиса по имени.
        Сначала ищет в service_registry, затем в общем реестре ресурсов.
        Поддерживает алиасы для обеспечения обратной совместимости.
        
        ARGS:
        - service_name: имя сервиса
        - timeout: время ожидания готовности сервиса в секундах (по умолчанию 5.0)

        RETURNS:
        - Экземпляр сервиса или None если сервис не найден или не готов
        """
        import asyncio
        from core.errors.service_not_ready import ServiceNotReadyError

        # Карта алиасов для обратной совместимости
        service_aliases = {
            "TableDescriptionService": "table_description_service",
            "table_description_service": "table_description_service",
        }

        # Нормализуем имя сервиса
        normalized_name = service_aliases.get(service_name, service_name)

        # Сначала ищем в service_registry
        service = self.service_registry.get(normalized_name)
        if service:
            return service

        # Затем ищем в общем реестре ресурсов
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            resource_info = self.registry.get_resource(normalized_name)
            if resource_info:
                # Проверяем, что resource_info - это ResourceInfo объект, а не просто инстанс
                if hasattr(resource_info, 'health') and hasattr(resource_info, 'instance'):
                    # Проверяем статус: возвращаем только сервисы со статусом HEALTHY
                    if resource_info.health == ResourceHealth.HEALTHY:
                        return resource_info.instance
                    elif resource_info.health == ResourceHealth.PENDING:
                        # Сервис еще не готов, ждем немного и пробуем снова
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        # Сервис в нездоровом состоянии
                        self.logger.warning(f"Сервис '{normalized_name}' в состоянии {resource_info.health}, доступ запрещен")
                        return None
                else:
                    # resource_info может быть самим сервисом (старый формат)
                    return resource_info

            # Если ресурс не найден, пробуем поискать по алиасам
            for alias, actual_name in service_aliases.items():
                if alias == service_name and alias != actual_name:
                    resource_info = self.registry.get_resource(actual_name)
                    if resource_info:
                        if hasattr(resource_info, 'health') and hasattr(resource_info, 'instance'):
                            if resource_info.health == ResourceHealth.HEALTHY:
                                return resource_info.instance
                            elif resource_info.health == ResourceHealth.PENDING:
                                # Сервис еще не готов, ждем немного и пробуем снова
                                await asyncio.sleep(0.1)
                                continue
                            else:
                                # Сервис в нездоровом состоянии
                                self.logger.warning(f"Сервис '{normalized_name}' в состоянии {resource_info.health}, доступ запрещен")
                                return None
                        else:
                            return resource_info

            # Если не найден, ждем немного и пробуем снова
            await asyncio.sleep(0.1)

        # Если после таймаута сервис не готов, бросаем исключение
        raise ServiceNotReadyError(f"Сервис '{service_name}' не стал готовым в течение {timeout} секунд")

    async def _initialize_infrastructure_services(self) -> None:
        """
        Инициализация всех зарегистрированных инфраструктурных сервисов.
        """
        for service_name, service in self.service_registry.items():
            try:
                success = await service.initialize()
                if not success:
                    self.logger.warning(f"Service {service_name} failed to initialize properly")

                # Публикация события инициализации сервиса
                await self.event_bus.publish(
                    EventType.SERVICE_INITIALIZED,
                    data={
                        "service_name": service_name,
                        "success": success,
                        "system_id": self.id
                    },
                    source="SystemContext._initialize_infrastructure_services",
                    correlation_id=self.id
                )
            except Exception as e:
                # Публикация события ошибки инициализации сервиса
                await self.event_bus.publish(
                    EventType.SYSTEM_ERROR,
                    data={
                        "service_name": service_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "system_id": self.id
                    },
                    source="SystemContext._initialize_infrastructure_services",
                    correlation_id=self.id
                )

    async def _shutdown_infrastructure_services(self) -> None:
        """
        Завершение работы всех зарегистрированных инфраструктурных сервисов.
        """
        for service_name, service in self.service_registry.items():
            try:
                await service.shutdown()

                # Публикация события завершения работы сервиса
                await self.event_bus.publish(
                    EventType.SERVICE_SHUTDOWN,
                    data={
                        "service_name": service_name,
                        "system_id": self.id
                    },
                    source="SystemContext._shutdown_infrastructure_services",
                    correlation_id=self.id
                )
            except Exception as e:
                # Публикация события ошибки завершения работы сервиса
                await self.event_bus.publish(
                    EventType.SYSTEM_ERROR,
                    data={
                        "service_name": service_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "system_id": self.id
                    },
                    source="SystemContext._shutdown_infrastructure_services",
                    correlation_id=self.id
                )
    
    async def _register_providers_from_config(self) -> None:
        """
        Автоматическая регистрация провайдеров из конфигурации.

        ЛОГИКА:
        1. Регистрация LLM провайдеров
        2. Регистрация DB провайдеров

        ОБРАБОТКА ОШИБОК:
        - Пропуск некорректных конфигураций
        - Публикация событий об ошибках создания провайдеров
        """
        # 1. Регистрация LLM провайдеров
        logger.info(f"Начинаем регистрацию LLM провайдеров. Найдено провайдеров: {len(self.config.llm_providers)}")
        first_provider_registered = False
        for provider_name, provider_config in self.config.llm_providers.items():
            logger.info(f"Обрабатываем провайдер: {provider_name}, тип: {type(provider_config)}, enabled: {getattr(provider_config, 'enabled', 'N/A')}")
            if provider_config.enabled:
                try:
                    logger.info(f"Пытаемся создать LLM провайдер: {provider_name}")
                    provider = await self.provider_factory.create_llm_provider_from_config(
                        provider_config,
                        provider_name
                    )
                    logger.info(f"Результат создания провайдера {provider_name}: {provider is not None}")
                    if provider:
                        # Регистрация LLM провайдера в системе
                        info_llm = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.LLM_PROVIDER,
                            instance=provider
                        )
                        # Устанавливаем первый успешно зарегистрированный провайдер как default
                        info_llm.is_default = not first_provider_registered
                        if not first_provider_registered:
                            first_provider_registered = True
                        self.registry.register_resource(info_llm)
                        logger.info(f"LLM провайдер '{provider_name}' успешно зарегистрирован")

                        # Публикация события регистрации провайдера
                        await self.event_bus.publish(
                            EventType.PROVIDER_REGISTERED,
                            data={
                                "provider_name": provider_name,
                                "provider_type": "LLM",
                                "system_id": self.id,
                                "is_default": info_llm.is_default
                            },
                            source="SystemContext._register_providers_from_config",
                            correlation_id=self.id
                        )
                    else:
                        logger.warning(f"Провайдер {provider_name} не был создан успешно")
                except Exception as e:
                    # Публикация события ошибки регистрации провайдера
                    await self.event_bus.publish(
                        EventType.SYSTEM_ERROR,
                        data={
                            "provider_name": provider_name,
                            "provider_type": "LLM",
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "system_id": self.id
                        },
                        source="SystemContext._register_providers_from_config",
                        correlation_id=self.id
                    )
                    logger.error(f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}", exc_info=True)
            else:
                logger.warning(f"Провайдер {provider_name} отключен (enabled={getattr(provider_config, 'enabled', 'N/A')})")

        # 2. Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    provider = await self.provider_factory.create_db_provider_from_config(
                        provider_config,
                        provider_name
                    )
                    if provider:
                        # Регистрация DB провайдера в системе
                        info_db = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.DATABASE,
                            instance=provider
                        )
                        info_db.is_default=True

                        self.registry.register_resource(info_db)

                        # Публикация события регистрации провайдера
                        await self.event_bus.publish(
                            EventType.PROVIDER_REGISTERED,
                            data={
                                "provider_name": provider_name,
                                "provider_type": "DATABASE",
                                "system_id": self.id
                            },
                            source="SystemContext._register_providers_from_config",
                            correlation_id=self.id
                        )
                except Exception as e:
                    # Публикация события ошибки регистрации провайдера
                    await self.event_bus.publish(
                        EventType.SYSTEM_ERROR,
                        data={
                            "provider_name": provider_name,
                            "provider_type": "DATABASE",
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "system_id": self.id
                        },
                        source="SystemContext._register_providers_from_config",
                        correlation_id=self.id
                    )
    
    def _get_resources_by_type(self, resource_type: ResourceType) -> Dict[str, ResourceInfo]:
        """
        Получение ресурсов заданного типа.

        ПАРАМЕТРЫ:
        - resource_type: Тип ресурсов для получения

        ВОЗВРАЩАЕТ:
        - Словарь {имя_ресурса: ResourceInfo} для ресурсов заданного типа
        """
        resources = {}
        all_resources = self.registry.all()

        for info in all_resources:
            if info.resource_type == resource_type:
                resources[info.name] = info

        return resources
    
    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение ресурса по имени.

        ПАРАМЕТРЫ:
        - name: Имя ресурса

        ВОЗВРАЩАЕТ:
        - Экземпляр ресурса если найден
        - None если ресурс не найден

        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        llm_provider = system.get_resource("primary_llm")
        if llm_provider:
            response = await llm_provider.generate(request)
        """
        # Карта алиасов для обеспечения обратной совместимости
        resource_aliases = {
            "table_description_service": "TableDescriptionService",
            "TableDescriptionService": "TableDescriptionService",
        }
        
        # Нормализуем имя ресурса
        normalized_name = resource_aliases.get(name, name)
        
        # Сначала ищем по нормальному имени
        resource = self.registry.get_resource(normalized_name)
        if resource:
            return resource
        
        # Если не найден, пробуем поискать по алиасам
        for alias, actual_name in resource_aliases.items():
            if alias == name and alias != actual_name:
                resource = self.registry.get_resource(actual_name)
                if resource:
                    return resource
        
        return None

    def get_capability(self, name: str) -> Optional[Capability]:
        """
        Получение capability по имени.

        ПАРАМЕТРЫ:
        - name: Имя capability

        ВОЗВРАЩАЕТ:
        - Capability объект если найден
        - None если capability не найдена

        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        cap = system.get_capability("planning.create_plan")
        if cap:
            print(f"Описание: {cap.description}")
        """
        return self.registry.get_capability(name)

    def list_capabilities(self) -> List[str]:
        """
        Получение списка всех доступных capability.

        ВОЗВРАЩАЕТ:
        - Список имен capability

        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        caps = system.list_capabilities()
        print(f"Доступные capability: {caps}")
        """
        return [cap.name for cap in self.registry.list_capabilities()]
    
    async def call_llm(
        self,
        request: LLMRequest
    ) -> Union[RawLLMResponse, StructuredLLMResponse]:
        """
        ЕДИНСТВЕННАЯ ТОЧКА ВЫЗОВА LLM ДЛЯ ВСЕЙ СИСТЕМЫ.
        
        ПОВЕДЕНИЕ:
        - Если request.structured_output is None → возвращает RawLLMResponse
        - Если request.structured_output is not None → возвращает StructuredLLMResponse[T]
          с гарантие���� валидности или выбрасывае���� StructuredOutputError
        
        АРХИТЕКТУРНЫЕ ГАРАНТИИ:
        1. Компоненты НЕ знают о ретраах — это скрыто внутри метода
        2. Валидация происходит ОДИН раз на уровне контекста
        3. События публикуются для каждой попытки (наблюдаемость)
        4. Обратная совместимость сохранена (сырые запросы работают как раньше)
        """
        correlation_id = request.correlation_id or str(uuid.uuid4())

        # Публикация события начала вызова LLM
        await self.event_bus.publish(
            EventType.LLM_CALL_STARTED,
            data={
                "prompt": request.prompt,
                "system_id": self.id,
                "structured_output": request.structured_output is not None
            },
            source="SystemContext.call_llm",
            correlation_id=correlation_id
        )

        default_llm = None
        for info in self.registry.all():
            if info.resource_type == ResourceType.LLM_PROVIDER and info.is_default:
                default_llm = info.instance
                break

        if default_llm is None:
            # Используем первый доступный LLM провайдер
            for info in self.registry.all():
                if info.resource_type == ResourceType.LLM_PROVIDER:
                    default_llm = info.instance
                    break

        if default_llm is None:
            # Публикация события ошибки
            await self.event_bus.publish(
                EventType.LLM_CALL_FAILED,
                data={
                    "error": "No available LLM providers",
                    "system_id": self.id
                },
                source="SystemContext.call_llm",
                correlation_id=correlation_id
            )
            raise ValueError("Нет доступных LLM провайдеров")

        # Базовый вызов провайдера (для получения метаданных)
        raw_response = await default_llm.generate(request)

        try:
            # 1. Если запрошена структурированная генерация и провайдер её поддерживает
            if request.structured_output is not None:
                # Проверяем, поддерживает ли провайдер нативную генерацию
                if hasattr(default_llm, 'generate_structured'):
                    try:
                        # Пытаемся использовать нативную генерацию структурированного вывода
                        structured_result = await default_llm.generate_structured(request)
                        
                        # Если нативная генерация успешна, возвращаем результат
                        # с признаком, что использовалась нативная валидация
                        from pydantic import BaseModel
                        
                        # Получаем модель для валидации
                        output_model = self._resolve_output_model(request.structured_output.output_model)
                        
                        # Валидируем результат с помощью Pydantic модели
                        validated_result = output_model.model_validate(structured_result)
                        
                        return StructuredLLMResponse(
                            parsed_content=validated_result,
                            raw_response=RawLLMResponse(
                                content=str(structured_result),  # Конвертируем в строку для совместимости
                                model=raw_response.model,
                                tokens_used=raw_response.tokens_used,
                                generation_time=raw_response.generation_time,
                                finish_reason=raw_response.finish_reason,
                                raw_provider_response=getattr(raw_response, 'raw_provider_response', None),
                                metadata=raw_response.metadata
                            ),
                            parsing_attempts=1,
                            validation_errors=[],
                            provider_native_validation=True  # Использовалась нативная валидация
                        )
                    except Exception as native_error:
                        # Если нативная генерация не удалась, переходим к резервной стратегии
                        logger.warning(f"Нативная генерация структурированного вывода не удалась: {native_error}")
                        # Продолжаем с резервной стратегии

            # 2. Если структурированный вывод не запрошен — возврат сырого ответа
            if request.structured_output is None:
                return RawLLMResponse(
                    content=raw_response.content,
                    model=raw_response.model,
                    tokens_used=raw_response.tokens_used,
                    generation_time=raw_response.generation_time,
                    finish_reason=raw_response.finish_reason,
                    raw_provider_response=getattr(raw_response, 'raw_provider_response', None),
                    metadata=raw_response.metadata
                )

            # 3. Обработка структурированного вывода с ретраями (резервная стратегия)
            return await self._handle_structured_output(
                request=request,
                initial_response=raw_response
            )
        except Exception as e:
            # Публикация события ошибки вызова LLM
            await self.event_bus.publish(
                EventType.LLM_CALL_FAILED,
                data={
                    "prompt": request.prompt,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "system_id": self.id
                },
                source="SystemContext.call_llm",
                correlation_id=correlation_id
            )
            raise

    async def create_agent(self, **kwargs):
        """
        Асинхронное создание агента.

        ПАРАМЕТРЫ:
        - **kwargs: Дополнительные параметры для AgentRuntime

        ВОЗВРАЩАЕТ:
        - Экземпляр AgentRuntime

        ПРИМЕР:
        # Создание агента с настройками по умолчанию
        agent = await factory.create()

        # Создание агента с кастомными параметрами
        agent = await factory.create(
            max_steps=20,
            temperature=0.5,
            session_context=existing_session
        )

        ОСОБЕННОСТИ:
        - Динамический импорт AgentRuntime для избежания циклических зависимостей
        - Создание SessionContext по умолчанию
        - Передача всех параметров напрямую в конструктор AgentRuntime

        ЗАМЕЧАНИЕ:
        - Метод всегда асинхронный, даже если создание агента синхронное
        - Не выполняет инициализацию агента, только создает экземпляр
        """
        correlation_id = str(uuid.uuid4())
        
        # Публикация события создания агента
        await self.event_bus.publish(
            EventType.AGENT_CREATED,
            data={
                "system_id": self.id,
                "parameters": {k: v for k, v in kwargs.items() if k != 'session_context'}  # Исключаем session_context из логов
            },
            source="SystemContext.create_agent",
            correlation_id=correlation_id
        )

        # Извлекаем специальные параметры из kwargs
        agent_config = kwargs.pop('agent_config', None)
        user_context = kwargs.pop('user_context', None)
        
        agent = AgentRuntime(
            system_context=self, 
            session_context=SessionContext(), 
            agent_config=agent_config,
            user_context=user_context,
            **kwargs
        )
        
        # Публикация с��бытия успешного создания агента
        await self.event_bus.publish(
            EventType.AGENT_CREATED,
            data={
                "system_id": self.id,
                "agent_id": getattr(agent, 'id', 'unknown'),
                "status": "created"
            },
            source="SystemContext.create_agent_complete",
            correlation_id=correlation_id
        )
        
        return agent

    
    async def create_agent_for_question(self, question: str, **kwargs):
        """
        Созда����т аген��а, настроенного под конкретный вопрос.
        
        Параметры:
        - question: вопрос/цель, которую должен решить агент
        - **kwargs: дополнительные параметры агента (max_steps, temperature и т.д.)
        
        Возвращ��ет:
        - Экземпляр агента, готовый к выполнению
        """
        # Выбор стратегии на основе типа вопроса
        strategy = await self._select_strategy_for_question(question)
        
        # Создание сессии с сохранением вопроса
        session_context = SessionContext()
        session_context.set_goal(question)
        
        # Настройка параметров агента
        agent_params = {
            "max_steps": kwargs.get("max_steps", self.config.agent.get("max_steps", 10)),
            "strategy": strategy,
            **{k: v for k, v in kwargs.items() if k not in ["max_steps"]}
        }
        
        # Извлекаем специальные параметры из agent_params
        agent_config = agent_params.pop('agent_config', None)
        user_context = agent_params.pop('user_context', None)
        
        # Создание агента
        return AgentRuntime(
            system_context=self,
            session_context=session_context,
            agent_config=agent_config,
            user_context=user_context,
            **agent_params
        )
    
    async def _execute_raw_sql_query(self, query: str, params: dict = {}, db_provider_name: str = "default_db", max_rows: int = 100):
        """
        Внутренний метод для выполнения SQL-запроса напрямую к базе данных.
        Используется сервисами, которые сами обеспечивают бе��опасность и валидацию.

        Параметры:
        - query: SQL-запрос
        - params: параметры запроса
        - db_provider_name: имя провайде��а БД
        - max_rows: максима��ьное количество возвращаемых строк

        Возвращает:
        - Результат выполнения в формате DBQueryResult
        """
        db_provider = self.get_resource(db_provider_name)
        if not db_provider:
            raise ValueError(f"DB провайдер '{db_provider_name}' не найден")

        if not hasattr(db_provider, "execute"):
            raise ValueError(f"Провайдер '{db_provider_name}' не поддерживает выполнение запросов")

        try:
            # Добавляем ограничение на количество строк, если это SELECT-запрос
            if query.strip().upper().startswith('SELECT'):
                # Пр����веряем, есть ли уже LIMIT в запросе
                if 'LIMIT' not in query.upper():
                    # Удаляем лишние пробелы и переносы строк в конце запроса перед добавлением LIMIT
                    query = query.rstrip().rstrip(';') + f" LIMIT {max_rows}"
            
            # Преобразуем параметры в нужный формат для провайдера
            if isinstance(params, list):
                # Если параметры переданы как список, передаем как кортеж
                provider_params = tuple(params)
            elif isinstance(params, dict):
                # Если параметры переданы как словарь, передаем как есть
                provider_params = params or {}
            else:
                # По умолчанию используем пустой словарь
                provider_params = {}
            
            result = await db_provider.execute(query, provider_params)
            logger.info(f"SQL з��прос выполнен успешно. Затронуто строк: {result.rowcount}")
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения SQL запроса: {str(e)}")
            raise

    async def execute_sql_query(self, query: str, params: dict = {}, db_provider_name: str = "default_db", max_rows: int = 1000):
        """
        Выполняет SQL-запрос к базе данных через безопасный сервис.
        Использует SQLQueryService для валидации и безопасного выполнения запроса.

        Параметры:
        - query: SQL-запрос
        - params: параметры запроса
        - db_provider_name: имя провайдера БД
        - max_rows: максимальное количество возвращаемых строк

        Возвращает:
        - Результат выполнения в формате DBQueryResult
        """
        # Получаем SQLQueryService для безопасного выполнения запроса
        sql_query_service = self.get_resource("sql_query_service")
        
        if sql_query_service:
            # Выполняем запрос через безопасный сервис
            try:
                result = await sql_query_service.execute_direct_query(
                    sql_query=query,
                    parameters=params,
                    max_rows=max_rows
                )
                return result
            except Exception as e:
                logger.warning(f"Ошибка выполнения запроса через SQLQueryService: {str(e)}, используем пр����ое вы��олнение")
                # В случае ошибки используем прямое выполнение как fallback
                return await self._execute_raw_sql_query(query, params, db_provider_name)
        else:
            logger.warning("SQLQueryService недоступен, используем прямое выполнение запроса")
            # Если сервис ����едоступен, и��пользуем прямое выполнение как fallback
            return await self._execute_raw_sql_query(query, params, db_provider_name)
    
    async def call_llm_with_params(
        self,
        user_prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        llm_provider_name: str = "default_llm",
        output_format: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Выполняет запрос к LLM с заданными параметрами.
        
        Параметры:
        - prompt: основной промпт
        - system_prompt: системный промпт
        - temperature: температура генерации
        - max_tokens: максимальное количество токенов
        - llm_provider_name: имя LLM провайдера
        - output_format: формат выходных данных (например, "json")
        - output_schema: JSON Schema для структурирования выходных данных
        - **kwargs: дополнительные параметры генерации
        
        Возвращает:
        - Результат генерации в формате LLMResponse
        """
        llm_provider = self.get_resource(llm_provider_name)
        if not llm_provider:
            raise ValueError(f"LLM провайдер '{llm_provider_name}' не найден")
        
        # Получаем параметры по умолчанию из конфигурации провайдера
        default_temperature = 0.7
        default_max_tokens = 2048

        if hasattr(llm_provider, "_config"):
            config = llm_provider._config
            default_temperature = getattr(config, "temperature", default_temperature)
            default_max_tokens = getattr(config, "max_tokens", default_max_tokens)
        elif hasattr(llm_provider, "config"):
            config = llm_provider.config
            # Проверяем, является ли config словарем или объектом с атрибутами
            if hasattr(config, 'get'):  # Это словарь
                default_temperature = config.get("temperature", default_temperature)
                default_max_tokens = config.get("max_tokens", default_max_tokens)
            else:  # Это объект с атрибутами
                default_temperature = getattr(config, "temperature", default_temperature)
                default_max_tokens = getattr(config, "max_tokens", default_max_tokens)
        
        temperature = temperature or default_temperature
        max_tokens = max_tokens or default_max_tokens
        
        try:
            if output_format == "json" and output_schema:
                
                # Определяем тип провайдера для правильного вызова метода
                provider_type = type(llm_provider).__name__
                logger.debug(f"Тип LLM провайдера: {provider_type}")
                
                # Выполняем структурированную генерацию в зависимости от типа провайдера
                if provider_type == "LlamaCppProvider":
                    # Для LlamaCppProvider используем user_prompt
                    return await llm_provider.generate_structured(
                        user_prompt=user_prompt,
                        output_schema=output_schema,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                else:
                    # Для остальных провайдеров (VLLMProvider) используем prompt
                    return await llm_provider.generate_structured(
                        user_prompt=user_prompt,
                        output_schema=output_schema,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
            else:
                # Стандартная генерация текста
                request = LLMRequest(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                response = await llm_provider.generate(request)
                logger.debug(f"LLM запрос выполнен за {response.generation_time:.2f} секунд")
                return response
                
        except Exception as e:
            logger.error(f"Ошибка выполнения LLM запроса: {str(e)}", exc_info=True)
            raise

    async def run_capability(
        self,
        capability_name: str,
        parameters: dict,
        session_context: BaseSessionContext = None
    ):
        """
        Выполняет конкретный навык с заданными параметрами.

        Параметры:
        - capability_name: имя capability для выполнения
        - parameters: параметры для capability
        - session_context: контекст сессии (если нет, создается новый)

        Возвращает:
        - Результат выполнения capability
        """
        correlation_id = str(uuid.uuid4())
        
        # Публикация события начала выполнения capability
        await self.event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            data={
                "capability_name": capability_name,
                "parameters": parameters,
                "system_id": self.id
            },
            source="SystemContext.run_capability",
            correlation_id=correlation_id
        )

        # Создаем контекст сессии при необходимости
        if session_context is None:
            # Публикация события ошибки
            await self.event_bus.publish(
                EventType.ERROR_OCCURRED,
                data={
                    "capability_name": capability_name,
                    "error": "Session context not provided",
                    "system_id": self.id
                },
                source="SystemContext.run_capability",
                correlation_id=correlation_id
            )
            raise ValueError(f"Ошибка запуска умения '{capability_name}', непередан контекст.")

        try:
            # Используем ExecutionGateway для выполнения capability
            result = await self.execution_gateway.execute_capability(
                capability_name = capability_name,
                parameters = parameters,
                system_context = self,
                session_context = session_context
            )
            
            # Публикация события успешного выполнения capability
            await self.event_bus.publish(
                EventType.SKILL_EXECUTED,
                data={
                    "capability_name": capability_name,
                    "parameters": parameters,
                    "result_status": "success",
                    "system_id": self.id
                },
                source="SystemContext.run_capability",
                correlation_id=correlation_id
            )
            
            return result
        except Exception as e:
            # Публикация события ошибки выполнения capability
            await self.event_bus.publish(
                EventType.ERROR_OCCURRED,
                data={
                    "capability_name": capability_name,
                    "parameters": parameters,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "system_id": self.id
                },
                source="SystemContext.run_capability",
                correlation_id=correlation_id
            )
            raise
    
    async def _handle_structured_output(
        self,
        request: LLMRequest,
        initial_response: Any  # Сырой ответ от провайдера
    ) -> StructuredLLMResponse:
        """Внутренняя реализация с ретраями и валидацией"""
        structured_config = request.structured_output
        max_retries = structured_config.max_retries
        attempts = []
        current_prompt = request.system_prompt or request.prompt
        
        # Получение реальной Pydantic модели по имени (из реестра моделей)
        output_model = self._resolve_output_model(structured_config.output_model)
        
        for attempt in range(max_retries):
            try:
                # Парсинг ответа
                parsed = output_model.model_validate_json(initial_response.content)
                
                # Публикация события успеха
                await self._publish_structured_success_event(
                    request=request,
                    model_name=structured_config.output_model,
                    attempt=attempt + 1,
                    parsed_model=parsed
                )
                
                return StructuredLLMResponse(
                    parsed_content=parsed,
                    raw_response=RawLLMResponse(
                        content=initial_response.content,
                        model=initial_response.model,
                        tokens_used=initial_response.tokens_used,
                        generation_time=initial_response.generation_time,
                        finish_reason=initial_response.finish_reason,
                        raw_provider_response=getattr(initial_response, 'raw_provider_response', None),
                        metadata=initial_response.metadata
                    ),
                    parsing_attempts=attempt + 1,
                    validation_errors=attempts,
                    provider_native_validation=False  # По умолчанию считаем, что валидация происходит на нашей стороне
                )
                
            except (ValidationError, json.JSONDecodeError) as e:
                error_detail = self._extract_validation_error(e, output_model)
                attempts.append(error_detail)
                
                # Публикация события ошибки
                await self._publish_structured_failure_event(
                    request=request,
                    model_name=structured_config.output_model,
                    attempt=attempt + 1,
                    max_attempts=max_retries,
                    error=error_detail
                )
                
                # Ретрай с уточняющим промптом (если есть попытки)
                if attempt < max_retries - 1:
                    # Формирование уточняющего промпта через централизованный сервис
                    prompt_service = self.get_resource("prompt_service")
                    if prompt_service:
                        correction_prompt = await prompt_service.render(
                            capability_name="structured_output.correction_hint",
                            variables={
                                "original_prompt": current_prompt,
                                "error_details": self._format_error_for_prompt(error_detail),
                                "expected_schema": json.dumps(structured_config.schema_def, indent=2)
                            }
                        )
                    else:
                        # Если нет prompt_service, используем базовый уточняющий промпт
                        correction_prompt = f"""
                        {current_prompt}
                        
                        ПРЕДЫДУЩИЙ ОТВЕТ БЫЛ НЕКОРРЕКТНЫМ:
                        {initial_response.content}
                        
                        ОШИБКА ВАЛИДАЦИИ:
                        {self._format_error_for_prompt(error_detail)}
                        
                        ПОЖАЛУЙСТА, ВЕРНИ ОТВЕТ В СТРОГО ОПРЕДЕЛЕННОМ ФОРМАТЕ СХЕМЫ:
                        {json.dumps(structured_config.schema_def, indent=2)}
                        """
                    
                    # Повторный вызов с уточненным промптом
                    retry_request = LLMRequest(
                        prompt=request.prompt,
                        system_prompt=correction_prompt,
                        temperature=request.temperature * 0.9,  # Снижаем креативность для точности
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                        stream=request.stream,
                        structured_output=structured_config,
                        metadata=request.metadata,
                        correlation_id=request.correlation_id,
                        capability_name=request.capability_name
                    )
                    
                    # Получаем LLM провайдер
                    default_llm = None
                    for info in self.registry.all():
                        if info.resource_type == ResourceType.LLM_PROVIDER and info.is_default:
                            default_llm = info.instance
                            break

                    if default_llm is None:
                        for info in self.registry.all():
                            if info.resource_type == ResourceType.LLM_PROVIDER:
                                default_llm = info.instance
                                break

                    if default_llm is None:
                        raise ValueError("Нет доступных LLM провайдеров")

                    initial_response = await default_llm.generate(retry_request)
                    current_prompt = correction_prompt
                    continue
                else:
                    # Исчерпаны все попытки
                    raise StructuredOutputError(
                        message=f"Не удалось получить валидный структурированный вывод после {max_retries} попыток",
                        model_name=structured_config.output_model,
                        attempts=attempts,
                        correlation_id=request.correlation_id or "unknown"
                    )
    
    def _resolve_output_model(self, model_name: str) -> Type[PydanticBaseModel]:
        """
        Разрешение имени модели в реальный класс.
        РЕАЛИЗАЦИЯ: реестр моделей или динамический импорт из безопасного списка.
        """
        # Пример реализации через реестр
        from core.application.services.sql_generation.schema import SQLGenerationOutput, SQLCorrectionOutput
        
        registry = {
            "SQLGenerationOutput": SQLGenerationOutput,
            "SQLCorrectionOutput": SQLCorrectionOutput,
            "AgentAction": None,  # Заглушка - будет добавлена при необходимости
            "ToolResponse": None,  # Заглушка - будет добавлена при необходимости
            # ... другие модели
        }
        
        # Попробуем найти модель в реестре
        if model_name in registry and registry[model_name] is not None:
            return registry[model_name]
        
        # Если не найдено в реестре, пробуем динамический импорт
        # Это позволяет использовать любую Pydantic модель, если она доступна
        try:
            # Попробуем импортировать из известных мест
            if model_name == "SQLGenerationOutput":
                from core.application.services.sql_generation.schema import SQLGenerationOutput
                return SQLGenerationOutput
            elif model_name == "SQLCorrectionOutput":
                from core.application.services.sql_generation.schema import SQLCorrectionOutput
                return SQLCorrectionOutput
        except ImportError:
            pass
        
        if model_name not in registry:
            raise ValueError(f"Неизвестная модель для структурированного вывода: {model_name}")
        
        raise ValueError(f"Модель {model_name} не может быть разрешена")
    
    def _extract_validation_error(self, error: Exception, model: Type[PydanticBaseModel]) -> Dict[str, Any]:
        """Извлечение деталей ошибки валидации"""
        if isinstance(error, ValidationError):
            return {
                "type": "validation_error",
                "details": error.errors(),
                "model_name": model.__name__
            }
        elif isinstance(error, json.JSONDecodeError):
            return {
                "type": "json_decode_error",
                "line": error.lineno,
                "col": error.colno,
                "message": str(error.msg),
                "model_name": model.__name__
            }
        else:
            return {
                "type": "unknown_error",
                "message": str(error),
                "model_name": model.__name__
            }
    
    def _format_error_for_prompt(self, error_detail: Dict[str, Any]) -> str:
        """Форматирование ошибки для включения в промпт коррекции"""
        if error_detail["type"] == "validation_error":
            errors_str = "\n".join([
                f"- Поле '{err['loc'][0]}': {err['msg']}" 
                for err in error_detail["details"]
            ])
            return f"Ошибки валидации: {errors_str}"
        elif error_detail["type"] == "json_decode_error":
            return f"Ошибка парсинга JSON: {error_detail['message']} на с��роке {error_detail.get('line', '?')}, колонке {error_detail.get('col', '?')}"
        else:
            return f"Неизвестная ошибка: {error_detail['message']}"
    
    async def _publish_structured_success_event(self, request: LLMRequest, model_name: str, attempt: int, parsed_model: Any):
        """Публикация события успешного структурированного вывода"""
        await self.event_bus.publish(
            EventType.LLM_CALL_COMPLETED,
            data={
                "request_type": "structured_output",
                "model_name": model_name,
                "attempt": attempt,
                "success": True,
                "parsed_fields": list(parsed_model.model_fields.keys()) if hasattr(parsed_model, 'model_fields') else [],
                "system_id": self.id
            },
            source="SystemContext._handle_structured_output",
            correlation_id=request.correlation_id or str(uuid.uuid4())
        )
    
    async def _publish_structured_failure_event(self, request: LLMRequest, model_name: str, attempt: int, max_attempts: int, error: Dict[str, Any]):
        """Публикация события неудачного структурированного вывода"""
        await self.event_bus.publish(
            EventType.LLM_CALL_FAILED,
            data={
                "request_type": "structured_output",
                "model_name": model_name,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "success": False,
                "error": error,
                "system_id": self.id
            },
            source="SystemContext._handle_structured_output",
            correlation_id=request.correlation_id or str(uuid.uuid4())
        )

    async def create_component_variant(
        self,
        base_component_name: str,
        variant_config: ComponentConfig,
        variant_name: Optional[str] = None
    ) -> str:
        """
        Создание варианта компонента с кастомной конфигурацией версий.

        ВАЖНО: Все промпты и контракты загружаются единожды при инициализации варианта.
        После этого экземпляр работает автономно без обращения к глобальным сервисам.

        :param base_component_name: Имя базового компонента ("planning", "book_library")
        :param variant_config: Конфигурация версий (с разделением input/output контрактов)
        :param variant_name: Уникальное имя варианта (формат "базовый@идентификатор")
        :return: Имя зарегистрированного варианта

        Пример:
            variant_name = await system_context.create_component_variant(
                base_component_name="planning",
                variant_config=ComponentConfig(
                    prompt_versions={"planning.create_plan": "v1.0.0"},
                    input_contract_versions={"planning.create_plan": "v1.0.0"},
                    output_contract_versions={"planning.create_plan": "v1.0.0"},
                    variant_id="beta-v1.0"
                )
            )
            # variant_name = "planning@beta-v1.3"
        """
        # Делегируем создание варианта фабрике провайдеров
        return await self.provider_factory.create_component_variant(
            base_component_name=base_component_name,
            variant_config=variant_config,
            variant_name=variant_name
        )

    async def _select_strategy_for_question(self, question: str) -> str:
        """
        Выбирает стратегию выполнения на основе типа вопроса.
        """
        # Создаем временный экземпляр AgentRuntime для использования его метода выбора стратегии
        # Это позволяет использовать ту же логику, что и в runtime
        temp_runtime = AgentRuntime(
            system_context=self,
            session_context=SessionContext(),
            max_steps=1  # Минимальное значение для инициализации
        )

        # Используем метод выбора стратегии из AgentRuntime
        selected_strategy = await temp_runtime._select_initial_strategy(question)

        return selected_strategy

    async def create_isolated_context(
        self, 
        variant_config: Dict[str, ComponentConfig],
        profile: Literal["prod", "sandbox"] = "prod"
    ) -> 'SystemContext':
        """
        Создаёт изолированный контекст с:
        - Собственными экземплярами навыков/инструментов (через create_component_variant)
        - Общими провайдерами (LLM, БД) — для эффективности
        - Изолированными кэшами промптов/контрактов
        """
        from copy import deepcopy
        from typing import Literal
        
        # Создаем новый экземпляр SystemContext с копией конфигурации
        new_config = deepcopy(self.config)
        
        # Обновляем профиль, если указан
        if profile == "sandbox":
            new_config.profile = "sandbox"
        
        # Создаем новый контекст
        isolated_context = SystemContext(config=new_config)
        
        # Копируем провайдеров (но не создаем новые соединения)
        # Провайдеры будут общими для эффективности
        for resource_info in self.registry.all():
            if resource_info.resource_type in [ResourceType.LLM_PROVIDER, ResourceType.DATABASE]:
                # Копируем ссылки на провайдеров, но не дублируем соединения
                isolated_context.registry.register_resource(resource_info)
        
        # Инициализируем провайдеров в новом контексте
        # Регистрируем провайдеров из конфигурации
        await isolated_context._register_providers_from_config()
        
        # Инициализируем основные сервисы в изолированном контексте
        await isolated_context.initialize()
        
        # Создаем изолированные компоненты (навыки, инструменты, сервисы) с вариантами
        for component_name, component_config in variant_config.items():
            # Создаем вариант компонента с изолированной конфигурацией
            await isolated_context.create_component_variant(
                base_component_name=component_name,
                variant_config=component_config
            )
        
        return isolated_context