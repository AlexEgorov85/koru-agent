"""
Фабрика компонентов - создание и инициализация компонентов с внедрением зависимостей.

[REFACTOR v5.4.0] Архитектура загрузки ресурсов:
1. ComponentFactory создаёт ResourcePreloader
2. ResourcePreloader загружает ресурсы через DataRepository
3. component_config.resolved_* заполняются объектами Prompt/Contract
4. Компонент создаётся с готовыми ресурсами

АРХИТЕКТУРА:
- Получение провайдеров из InfrastructureContext
- Передача интерфейсов напрямую в конструкторы компонентов
- Никаких DI контейнеров - только прямая передача зависимостей

USAGE:
```python
factory = ComponentFactory(infrastructure_context)
component = await factory.create_and_initialize(
    component_class=MySkill,
    name="my_skill",
    application_context=app_context,
    component_config=config,
    executor=executor
)
```
"""
from typing import Type, Any, Optional, TYPE_CHECKING
from core.config.component_config import ComponentConfig
from core.agent.components.base_component import BaseComponent
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

if TYPE_CHECKING:
    from core.application_context.application_context import ApplicationContext


class ComponentFactory:
    """Фабрика для создания и инициализации компонентов с DI."""

    def __init__(self, infrastructure_context: InfrastructureContext):
        """
        Инициализация фабрики.

        ARGS:
        - infrastructure_context: Инфраструктурный контекст для получения провайдеров
        """
        self._infrastructure_context = infrastructure_context
        self.event_bus_logger = None
        self._resource_preloader = None  # Будет создан при необходимости
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger."""
        if self._infrastructure_context and self._infrastructure_context.event_bus:
            self.event_bus_logger = EventBusLogger(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self._infrastructure_context.event_bus,
                session_id="system",
                agent_id="system",
                component="ComponentFactory"
            )

    def _get_resource_preloader(self, application_context: ApplicationContext):
        """
        Получить или создать ResourcePreloader.

        [REFACTOR v5.4.0] ResourcePreloader создаётся лениво при первой необходимости.

        ARGS:
        - application_context: ApplicationContext с data_repository

        RETURNS:
        - ResourcePreloader
        """
        if self._resource_preloader is None:
            from core.services.preloading.resource_preloader import ResourcePreloader

            self._resource_preloader = ResourcePreloader(
                data_repository=application_context.data_repository,
                event_bus=self._infrastructure_context.event_bus
            )

        return self._resource_preloader

    async def _log_info(self, message: str, *args, **kwargs):
        """Информационное сообщение."""
        if self.event_bus_logger:
            await self.event_bus_logger.info(message, *args, **kwargs)
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    async def _log_error(self, message: str, *args, **kwargs):
        """Ошибка."""
        if self.event_bus_logger:
            await self.event_bus_logger.error(message, *args, **kwargs)
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def _get_providers(self) -> dict:
        """
        Получить все провайдеры из инфраструктурного контекста.

        [REFACTOR Этап 7] db, llm, cache, vector удалены — не нужны для BaseComponent

        RETURNS:
        - dict: Словарь с провайдерами по именам
        """
        providers = {}
        infra = self._infrastructure_context

        # [REFACTOR Этап 7] Получаем только необходимые интерфейсы
        # Хранилища
        if hasattr(infra, 'prompt_storage'):
            providers['prompt_storage'] = infra.prompt_storage

        if hasattr(infra, 'contract_storage'):
            providers['contract_storage'] = infra.contract_storage

        # Шина событий
        if hasattr(infra, 'event_bus'):
            providers['event_bus'] = infra.event_bus

        # Хранилища метрик и логов
        if hasattr(infra, 'metrics_storage'):
            providers['metrics_storage'] = infra.metrics_storage
        
        if hasattr(infra, 'log_storage'):
            providers['log_storage'] = infra.log_storage
        
        return providers

    async def create_and_initialize(
        self,
        component_class: Type[BaseComponent],
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: 'ActionExecutor'
    ) -> BaseComponent:
        """
        Создание и инициализация компонента с внедрением зависимостей.

        [REFACTOR v5.4.0] АРХИТЕКТУРА:
        1. ResourcePreloader загружает ресурсы через DataRepository
        2. component_config.resolved_* заполняются объектами Prompt/Contract
        3. Получаем провайдеры из InfrastructureContext
        4. Передаём их в конструктор компонента как интерфейсы
        5. Компонент не зависит от контекстов напрямую

        ARGS:
        - component_class: класс компонента для создания
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента
        - executor: ActionExecutor для взаимодействия между компонентами

        RETURNS:
        - BaseComponent: созданный и инициализированный компонент
        """
        await self._log_info(f"Создание компонента {name} типа {component_class.__name__}")

        # [REFACTOR v5.4.0] 1. Загружаем ресурсы ДО создания компонента
        preloader = self._get_resource_preloader(application_context)
        
        # Логирование через event_bus
        event_bus = self._infrastructure_context.event_bus
        await event_bus.publish(EventType.DEBUG, {"message": f"🏭 ComponentFactory: preload_for_component({name})..."})
        
        resources = await preloader.preload_for_component(name, component_config)
        
        await event_bus.publish(EventType.DEBUG, {
            "message": f"🏭 ComponentFactory: resources: prompts={len(resources['prompts'])}, input={len(resources['input_contracts'])}, output={len(resources['output_contracts'])}"
        })

        # 2. Заполняем component_config.resolved_* загруженными ресурсами
        component_config.resolved_prompts = resources["prompts"]
        component_config.resolved_input_contracts = resources["input_contracts"]
        component_config.resolved_output_contracts = resources["output_contracts"]

        await self._log_info(
            f"Ресурсы загружены для {name}: "
            f"промптов={len(resources['prompts'])}, "
            f"input_contracts={len(resources['input_contracts'])}, "
            f"output_contracts={len(resources['output_contracts'])}"
        )

        # 3. Получаем провайдеры из инфраструктурного контекста
        providers = self._get_providers()

        await self._log_info(
            f"Получены провайдеры для {name}: " +
            ", ".join([k for k, v in providers.items() if v is not None])
        )

        # 4. Анализируем сигнатуру конструктора компонента
        import inspect
        sig = inspect.signature(component_class.__init__)
        params = sig.parameters

        # 5. Формируем аргументы для конструктора
        kwargs = {
            'name': name,
            'component_config': component_config,  # ← С УЖЕ заполненными resolved_*
            'executor': executor
        }

        # 6. Передаем провайдеры как интерфейсы
        # Если компонент принимает application_context - передаём (для обратной совместимости)
        if 'application_context' in params:
            kwargs['application_context'] = application_context

        # Передаем event_bus для логирования
        # metrics_storage и log_storage НЕ передаются — они подписаны на EventBus
        # и автоматически получают события
        if providers.get('event_bus'):
            kwargs['event_bus'] = providers['event_bus']
        
        # 5. Специальная обработка для behavior patterns
        from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
        if issubclass(component_class, BaseBehaviorPattern):
            await self._log_info(f"Создание behavior pattern {component_class.__name__} с component_name={name}")
            # Для behavior patterns используем component_name вместо name
            if 'component_name' in params:
                kwargs['component_name'] = name
                del kwargs['name']
        
        # 6. Создаём компонент
        await self._log_info(
            f"Создание {component_class.__name__} с параметрами: " +
            ", ".join([f"{k}={type(v).__name__}" for k, v in kwargs.items() if v is not None])
        )
        
        component = component_class(**kwargs)
        
        await self._log_info(f"Компонент {name} создан (инициализация будет выполнена позже)")
        
        # 7. НЕ вызываем initialize() здесь!
        # Инициализация будет выполнена в _initialize_components_with_dependencies()
        # Это гарантирует, что все зависимости уже зарегистрированы в контексте
        
        return component

    async def _resolve_component_class(self, component_type: str, name: str) -> Type[BaseComponent]:
        """
        Разрешение класса компонента через динамическое обнаружение.

        Все компоненты обнаружаются автоматически через сканирование файловой системы.
        Никакого хардкода — ComponentDiscovery находит классы по структуре директорий.

        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента

        RETURNS:
        - Type[BaseComponent]: класс компонента
        """
        await self._log_info(f"Разрешение класса компонента: тип={component_type}, имя={name}")

        discovery = self._get_discovery()
        entry = discovery.find_component(component_type, name)

        if entry is not None:
            await self._log_info(
                f"Найден компонент (динамически): {entry.class_name} "
                f"в {entry.file_path}"
            )
            return entry.class_ref

        await self._log_error(
            f"Компонент {component_type}/{name} не найден. "
            f"Доступные: {discovery.get_all_names()}"
        )
        raise ValueError(f"Компонент {component_type}/{name} не найден")

    def _get_discovery(self) -> "ComponentDiscovery":
        """Получить или создать экземпляр ComponentDiscovery."""
        if not hasattr(self, "_component_discovery"):
            from core.agent.components.component_discovery import ComponentDiscovery
            self._component_discovery = ComponentDiscovery()
        return self._component_discovery

    async def create_by_name(
        self,
        component_type: str,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: 'ActionExecutor'
    ) -> BaseComponent:
        """
        Создание компонента по имени и типу.
        
        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента
        - executor: ActionExecutor для взаимодействия между компонентами
        
        RETURNS:
        - BaseComponent: созданный и инициализированный компонент
        """
        await self._log_info(f"ComponentFactory: создание компонента {name} типа {component_type}")
        component_class = await self._resolve_component_class(component_type, name)
        await self._log_info(f"ComponentFactory: найден класс {component_class.__name__} для {name}")
        result = await self.create_and_initialize(
            component_class=component_class,
            name=name,
            application_context=application_context,
            component_config=component_config,
            executor=executor
        )
        await self._log_info(f"ComponentFactory: компонент {name} успешно создан")
        return result
