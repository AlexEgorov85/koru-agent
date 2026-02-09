"""
Упрощенный системный контекст (SystemContext).
ОСОБЕННОСТИ:
- Минимальная сложность
- Отсутствие циклических зависимостей
- Явный порядок инициализации
- Простота понимания и поддержки
- Интеграция с шиной событий для замены логирования
"""
import uuid
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from core.agent_runtime.runtime import AgentRuntime
from core.config.models import SystemConfig
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.session_context import SessionContext
from core.system_context.base_system_contex import BaseSystemContext
from core.system_context.execution_gateway import ExecutionGateway
from core.system_context.resource_registry import ResourceRegistry, ResourceInfo
from core.system_context.capability_registry import CapabilityRegistry
from core.system_context.lifecycle_manager import LifecycleManager

from core.infrastructure.providers.factory import ProviderFactory
from models.capability import Capability
from models.llm_types import LLMRequest, LLMResponse, RawLLMResponse, StructuredLLMResponse, StructuredOutputConfig
from models.resource import ResourceType
from core.errors.structured_output import StructuredOutputError
from pydantic import ValidationError
from pydantic.main import BaseModel as PydanticBaseModel
import json

# Импорты для инфраструктурных сервисов
from core.infrastructure.service.base_service import BaseService
from core.infrastructure.service.prompt_service import PromptService
from core.infrastructure.service.sql_generation.service import SQLGenerationService
from core.infrastructure.service.sql_query.service import SQLQueryService
from core.infrastructure.service.sql_validator.service import SQLValidatorService
from typing import Type, Dict

# Импорты для шины событий
from core.events.event_bus import EventBus, EventType, get_event_bus, Event
from core.events.event_handlers import LoggingEventHandler, MetricsEventHandler, AuditEventHandler

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
        Инициализация системного контекста.

        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (опционально)

        СОЗДАВАЕМЫЕ КОМПОНЕНТЫ:
        - registry: Реестр ресурсов
        - capabilities: Реестр capability
        - lifecycle: Менеджер жизненного цикла
        - config: Конфигурация
        - provider_factory: Фабрика провайдеров
        - event_bus: Шина событий

        ОСОБЕННОСТИ:
        - Создает все необходимые внутренние компоненты
        - Не выполняет их инициализацию (только создание)
        - Готов к регистрации ресурсов сразу после создания
        """
        self.id = str(uuid.uuid4())
        self.config = config or SystemConfig()
        # === ЕДИНСТВЕННЫЙ реестр для ВСЕХ компонентов ===
        self.registry = ResourceRegistry()  # ← Теперь управляет и ресурсами, и capability
        self.lifecycle = LifecycleManager(self.registry)  # ← Передаём ЕДИНЫЙ реестр
        self.initialized = False
        self.execution_gateway = ExecutionGateway()

        # Инициализация фабрики провайдеров
        self.provider_factory = ProviderFactory(self)

        # Инициализация реестра инфраструктурных сервисов
        self.service_registry = {}

        # Инициализация шины событий
        self.event_bus = get_event_bus()
        self._setup_event_handlers()

        # Настройка логирования (временно для совместимости)
        self._setup_logging()

        # Публикация события создания системного контекста (временно без await)
        # Так как __init__ не может быть async, мы не можем использовать await здесь
        # Это событие будет отправлено в асинхронном методе initialize
        # await self.event_bus.publish(
        #     EventType.SYSTEM_INITIALIZED,
        #     data={"system_id": self.id, "config_profile": self.config.profile},
        #     source="SystemContext.__init__",
        #     correlation_id=self.id
        # )
    
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
        self.logging_handler = LoggingEventHandler(
            log_dir=self.config.log_dir or "logs"
        )
        self.metrics_handler = MetricsEventHandler()
        self.audit_handler = AuditEventHandler(
            audit_log_dir=os.path.join(self.config.log_dir or "logs", "audit")
        )
        
        # Подписка обработчиков на события
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self.logging_handler.handle_event)
            self.event_bus.subscribe(event_type, self.metrics_handler.handle_event)
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
        """Инициализация системы."""
        try:
            # Публикация события создания и начала инициализации системного контекста
            await self.event_bus.publish(
                EventType.SYSTEM_INITIALIZED,
                data={
                    "system_id": self.id,
                    "config_profile": self.config.profile,
                    "profile": self.config.profile,
                    "timestamp": datetime.now().isoformat()
                },
                source="SystemContext.initialize",
                correlation_id=self.id
            )

            initialization_errors = []

            # 1. Автоматическая регистрация провайдеров из конфигурации
            try:
                await self._register_providers_from_config()
            except Exception as e:
                logger.warning(f"Ошибка регистрации провайдеров: {str(e)}")
                initialization_errors.append(f"Providers registration failed: {str(e)}")

            # 2. Создание и регистрация PromptService
            try:
                prompt_service = PromptService(
                    prompts_dir=getattr(self.config, 'prompts_dir', "prompts"),
                    default_version=getattr(self.config, 'prompts_default_version', "v1.2.0"),
                    system_context=self
                )
                await prompt_service.initialize()

                resource_info = ResourceInfo(
                    name="prompt_service",
                    resource_type=ResourceType.SERVICE,
                    instance=prompt_service
                )
                resource_info.is_default = True
                self.registry.register_resource(resource_info)
            except Exception as e:
                logger.warning(f"Ошибка инициализации PromptService: {str(e)}")
                initialization_errors.append(f"PromptService initialization failed: {str(e)}")

            # 3. Создание и регистрация SQLGenerationService
            try:
                sql_generation_service = SQLGenerationService(self)
                await sql_generation_service.initialize()

                resource_info = ResourceInfo(
                    name="sql_generation_service",
                    resource_type=ResourceType.SERVICE,
                    instance=sql_generation_service
                )
                resource_info.is_default = True
                self.registry.register_resource(resource_info)
                
                # Также регистрируем в service_registry для обратной совместимости
                await self.register_service("sql_generation_service", sql_generation_service)
            except Exception as e:
                logger.warning(f"Ошибка инициализации SQLGenerationService: {str(e)}")
                initialization_errors.append(f"SQLGenerationService initialization failed: {str(e)}")

            # 4. Создание и регистрация SQLValidatorService
            try:
                sql_validator_service = SQLValidatorService(self, allowed_operations=["SELECT"])
                await sql_validator_service.initialize()

                resource_info = ResourceInfo(
                    name="sql_validator_service",
                    resource_type=ResourceType.SERVICE,
                    instance=sql_validator_service
                )
                resource_info.is_default = True
                self.registry.register_resource(resource_info)
            except Exception as e:
                logger.warning(f"Ошибка инициализации SQLValidatorService: {str(e)}")
                initialization_errors.append(f"SQLValidatorService initialization failed: {str(e)}")

            # 5. Создание и регистрация SQLQueryService
            try:
                sql_query_service = SQLQueryService(self)
                await sql_query_service.initialize()

                resource_info = ResourceInfo(
                    name="sql_query_service",
                    resource_type=ResourceType.SERVICE,
                    instance=sql_query_service
                )
                resource_info.is_default = True
                self.registry.register_resource(resource_info)
            except Exception as e:
                logger.warning(f"Ошибка инициализации SQLQueryService: {str(e)}")
                initialization_errors.append(f"SQLQueryService initialization failed: {str(e)}")

            # 6. Автоматическая регистрация инфраструктурных сервисов из директории
            try:
                await self.provider_factory.discover_and_create_all_services()
            except Exception as e:
                logger.warning(f"Ошибка регистрации сервисов: {str(e)}")
                initialization_errors.append(f"Services registration failed: {str(e)}")

            # 5. Автоматическая регистрация инструментов из директории
            try:
                await self.provider_factory.discover_and_create_all_tools()
            except Exception as e:
                logger.warning(f"Ошибка регистрации инструментов: {str(e)}")
                initialization_errors.append(f"Tools registration failed: {str(e)}")

            # 6. Автоматическая регистрация навыков из директории
            try:
                await self.provider_factory.discover_and_create_all_skills()
            except Exception as e:
                logger.warning(f"Ошибка регистрации навыков: {str(e)}")
                initialization_errors.append(f"Skills registration failed: {str(e)}")

            # 6. Инициализация всех компонентов
            try:
                initialization_success = await self.lifecycle.initialize()
                if not initialization_success:
                    await self.event_bus.publish(
                        EventType.ERROR_OCCURRED,
                        data={
                            "error": "Not all components were initialized successfully",
                            "system_id": self.id
                        },
                        source="SystemContext.initialize",
                        correlation_id=self.id
                    )
            except Exception as e:
                logger.warning(f"Ошибка инициализации компонентов: {str(e)}")
                initialization_errors.append(f"Components initialization failed: {str(e)}")

            # 7. Проверка здоровья системы
            try:
                health_report = await self.lifecycle.check_health()
                if health_report["status"] == "unhealthy":
                    await self.event_bus.publish(
                        EventType.SYSTEM_ERROR,
                        data={
                            "error": "System failed health check",
                            "health_report": health_report,
                            "system_id": self.id
                        },
                        source="SystemContext.initialize",
                        correlation_id=self.id
                    )
                    # Не возвращаем False здесь, чтобы позволить системе работать с частичной неудачей
            except Exception as e:
                logger.warning(f"Ошибка проверки здоровья системы: {str(e)}")
                initialization_errors.append(f"Health check failed: {str(e)}")

            # 8. Инициализация инфраструктурных сервисов
            try:
                await self._initialize_infrastructure_services()
            except Exception as e:
                logger.warning(f"Ошибка инициализации инфраструктурных сервисов: {str(e)}")
                initialization_errors.append(f"Infrastructure services initialization failed: {str(e)}")

            self.initialized = True

            # Публикация события успешной инициализации
            await self.event_bus.publish(
                EventType.SYSTEM_INITIALIZED,
                data={
                    "system_id": self.id,
                    "status": "initialized",
                    "profile": self.config.profile,
                    "initialization_errors": initialization_errors if initialization_errors else None
                },
                source="SystemContext.initialize_complete",
                correlation_id=self.id
            )

            # Возвращаем True, если инициализация прошла успешно хотя бы частично
            # Возвращаем False только если критические ошибки не позволяют системе работать
            return True

        except Exception as e:
            await self.event_bus.publish(
                EventType.SYSTEM_ERROR,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "system_id": self.id
                },
                source="SystemContext.initialize",
                correlation_id=self.id
            )
            return False
        
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

    async def get_service(self, service_name: str) -> Optional[BaseService]:
        """
        Получение инфраструктурного сервиса по имени.
        Сначала ищет в service_registry, затем в общем реестре ресурсов.

        ARGS:
        - service_name: имя сервиса

        RETURNS:
        - Экземпляр сервиса или None если сервис не найден
        """
        # Сначала ищем в service_registry
        service = self.service_registry.get(service_name)
        if service:
            return service
        
        # Затем ищем в общем реестре ресурсов
        resource_info = self.registry.get_resource(service_name)
        if resource_info and hasattr(resource_info, 'instance'):
            return resource_info.instance
        
        return None

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
        for provider_name, provider_config in self.config.llm_providers.items():
            if provider_config.enabled:
                try:
                    provider = await self.provider_factory.create_llm_provider_from_config(
                        provider_config,
                        provider_name
                    )
                    if provider:
                        # Регистрация LLM провайдера в системе
                        info_llm = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.LLM_PROVIDER,
                            instance=provider
                        )
                        info_llm.is_default=True # Нужно добавить проверку что именно первая LLM загружена
                        self.registry.register_resource(info_llm)
                        
                        # Публикация события регистрации провайдера
                        await self.event_bus.publish(
                            EventType.PROVIDER_REGISTERED,
                            data={
                                "provider_name": provider_name,
                                "provider_type": "LLM",
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
                            "provider_type": "LLM",
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "system_id": self.id
                        },
                        source="SystemContext._register_providers_from_config",
                        correlation_id=self.id
                    )

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
        
        for name, info in all_resources.items():
            if info.resource_type == resource_type:
                resources[name] = info
        
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
        return self.registry.get_resource(name)

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
          с гарантией валидности или выбрасывает StructuredOutputError
        
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

        agent = AgentRuntime(self, SessionContext(), **kwargs)
        
        # Публикация события успешного создания агента
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
        Создает агента, настроенного под конкретный вопрос.
        
        Параметры:
        - question: вопрос/цель, которую должен решить агент
        - **kwargs: дополнительные параметры агента (max_steps, temperature и т.д.)
        
        Возвращает:
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
        
        # Создание агента
        return AgentRuntime(
            system=self,
            session_context=session_context,
            **agent_params
        )
    
    async def _execute_raw_sql_query(self, query: str, params: dict = {}, db_provider_name: str = "default_db", max_rows: int = 100):
        """
        Внутренний метод для выполнения SQL-запроса напрямую к базе данных.
        Используется сервисами, которые сами обеспечивают безопасность и валидацию.

        Параметры:
        - query: SQL-запрос
        - params: параметры запроса
        - db_provider_name: имя провайдера БД
        - max_rows: максимальное количество возвращаемых строк

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
                # Проверяем, есть ли уже LIMIT в запросе
                if 'LIMIT' not in query.upper():
                    query = f"{query} LIMIT {max_rows}"
            
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
            logger.info(f"SQL запрос выполнен успешно. Затронуто строк: {result.rowcount}")
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
                logger.warning(f"Ошибка выполнения запроса через SQLQueryService: {str(e)}, используем прямое выполнение")
                # В случае ошибки используем прямое выполнение как fallback
                return await self._execute_raw_sql_query(query, params, db_provider_name)
        else:
            logger.warning("SQLQueryService недоступен, используем прямое выполнение запроса")
            # Если сервис недоступен, используем прямое выполнение как fallback
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
            default_temperature = config.get("temperature", default_temperature)
            default_max_tokens = config.get("max_tokens", default_max_tokens)
        
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
        from core.infrastructure.service.sql_generation.schema import SQLGenerationOutput, SQLCorrectionOutput
        
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
                from core.infrastructure.service.sql_generation.schema import SQLGenerationOutput
                return SQLGenerationOutput
            elif model_name == "SQLCorrectionOutput":
                from core.infrastructure.service.sql_generation.schema import SQLCorrectionOutput
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