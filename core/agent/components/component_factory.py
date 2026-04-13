"""
Фабрика компонентов - создание и инициализация компонентов с внедрением зависимостей.

Архитектура загрузки ресурсов:
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
from typing import Type, Any, Optional
import logging

from core.agent.components.component import Component
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging.event_types import LogEventType


class ComponentFactory:
    """Фабрика для создания и инициализации компонентов с DI."""

    def __init__(self, infrastructure_context: InfrastructureContext):
        """
        Инициализация фабрики.

        ARGS:
        - infrastructure_context: Инфраструктурный контекст для получения загрузчика ресурсов
        """
        self._infrastructure_context = infrastructure_context
        self._logger = logging.getLogger("component_factory")

    def _log_info(self, message: str):
        """Информационное сообщение (только в файл)."""
        self._logger.info(f"[ComponentFactory] {message}")

    def _log_error(self, message: str):
        """Ошибка."""
        self._logger.error(f"[ComponentFactory] {message}", extra={"event_type": LogEventType.SYSTEM_ERROR})

    def _get_providers(self) -> dict:
        """
        Получить все провайдеры из инфраструктурного контекста.

        db, llm, cache, vector удалены — не нужны для Component

        RETURNS:
        - dict: Словарь с провайдерами по именам
        """
        providers = {}
        infra = self._infrastructure_context

        # Получаем только необходимые интерфейсы
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
        component_class: Type[Component],
        name: str,
        application_context: 'ApplicationContext',
        component_config: 'ComponentConfig',
        executor: 'ActionExecutor'
    ) -> Component:
        """
        Создание и инициализация компонента с внедрением зависимостей.

        АРХИТЕКТУРА:
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
        - Component: созданный и инициализированный компонент
        """
        self._log_info(f"Создание компонента {name} типа {component_class.__name__}")

        # Загружаем ресурсы напрямую из ResourceLoader
        resource_loader = self._infrastructure_context.resource_loader
        if resource_loader is None:
            raise RuntimeError("ResourceLoader не инициализирован в InfrastructureContext")

        resources = resource_loader.get_component_resources(name, component_config)

        # 2. Заполняем component_config.resolved_* загруженными ресурсами
        component_config.resolved_prompts = resources["prompts"]
        component_config.resolved_input_contracts = resources["input_contracts"]
        component_config.resolved_output_contracts = resources["output_contracts"]

        self._log_info(
            f"Ресурсы загружены для {name}: "
            f"промптов={len(resources['prompts'])}, "
            f"input_contracts={len(resources['input_contracts'])}, "
            f"output_contracts={len(resources['output_contracts'])}"
        )

        # 3. Получаем провайдеры из инфраструктурного контекста
        providers = self._get_providers()

        self._log_info(
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

        # Передаём log_session для логирования компонентов
        if 'log_session' in params:
            kwargs['log_session'] = self._infrastructure_context.log_session

        # event_bus БОЛЬШЕ не передаётся — компоненты используют стандартный logging
        
        # 7. Специальная обработка для behavior patterns
        from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
        if issubclass(component_class, BaseBehaviorPattern):
            self._log_info(f"Создание behavior pattern {component_class.__name__} с component_name={name}")
            # Для behavior patterns используем component_name вместо name
            if 'component_name' in params:
                kwargs['component_name'] = name
                del kwargs['name']

        # 8. Создаём компонент
        self._log_info(
            f"Создание {component_class.__name__} с параметрами: " +
            ", ".join([f"{k}={type(v).__name__}" for k, v in kwargs.items() if v is not None])
        )
        
        component = component_class(**kwargs)
        
        self._log_info(f"Компонент {name} создан (инициализация будет выполнена позже)")
        
        # 7. НЕ вызываем initialize() здесь!
        # Инициализация будет выполнена в _initialize_components_with_dependencies()
        # Это гарантирует, что все зависимости уже зарегистрированы в контексте
        
        return component

    async def _resolve_component_class(self, component_type: str, name: str) -> Type[Component]:
        """
        Разрешение класса компонента через динамическое обнаружение.

        Все компоненты обнаружаются автоматически через сканирование файловой системы.
        Никакого хардкода — ComponentDiscovery находит классы по структуре директорий.

        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента

        RETURNS:
        - Type[Component]: класс компонента
        """
        self._log_info(f"Разрешение класса компонента: тип={component_type}, имя={name}")

        discovery = self._get_discovery()
        if not discovery._global_scanned:
            discovery.scan()

        normalized_name = self._normalize_component_name(component_type, name)
        if normalized_name != name:
            self._log_info(f"Нормализация имени: {name} -> {normalized_name}")

        entry = discovery.find_component(component_type, normalized_name)

        if entry is not None:
            self._log_info(
                f"Найден компонент (динамически): {entry.class_name} "
                f"в {entry.file_path}"
            )
            return entry.class_ref

        all_names = discovery.get_all_names()
        self._log_error(
            f"Компонент {component_type}/{name} (нормализовано: {normalized_name}) не найден. Доступные: {all_names}"
        )
        raise ValueError(f"Компонент {component_type}/{name} не найден")

    def _normalize_component_name(self, component_type: str, name: str) -> str:
        """
        Нормализация имени компонента к формату ComponentDiscovery.

        AppConfig.from_discovery() отдаёт имена с суффиксами:
        - services: contract_service -> contract
        - behaviors: evaluation_pattern -> evaluation
        - tools: vector_books -> vector_search_tool

        ARGS:
        - component_type: тип компонента
        - name: имя из AppConfig

        RETURNS:
        - str: нормализованное имя для поиска в ComponentDiscovery
        """
        if component_type == "service":
            if name.endswith("_service"):
                return name[: -len("_service")]
            return name

        if component_type == "behavior":
            if name.endswith("_pattern"):
                return name[: -len("_pattern")]
            return name

        if component_type == "tool":
            if not name.endswith("_tool"):
                candidate = f"{name}_tool"
                discovery = self._get_discovery()
                if discovery.find_component("tool", candidate):
                    return candidate
            return name

        return name

    def _get_discovery(self) -> 'ComponentDiscovery':
        """Получить или создать экземпляр ComponentDiscovery."""
        if not hasattr(self, "_component_discovery"):
            from core.agent.components.component_discovery import ComponentDiscovery
            # Передаём logger из infrastructure_context чтобы ошибки discovery
            # попадали в тот же файл лога (infra_context.log)
            discovery_logger = getattr(
                getattr(self._infrastructure_context, 'log_session', None),
                'infra_logger',
                None
            )
            self._component_discovery = ComponentDiscovery(logger=discovery_logger)
        return self._component_discovery

    async def create_by_name(
        self,
        component_type: str,
        name: str,
        application_context: 'ApplicationContext',
        component_config: 'ComponentConfig',
        executor: 'ActionExecutor'
    ) -> Component:
        """
        Создание компонента по имени и типу.
        
        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента
        - executor: ActionExecutor для взаимодействия между компонентами
        
        RETURNS:
        - Component: созданный и инициализированный компонент
        """
        self._log_info(f"ComponentFactory: создание компонента {name} типа {component_type}")
        component_class = await self._resolve_component_class(component_type, name)
        self._log_info(f"ComponentFactory: найден класс {component_class.__name__} для {name}")
        result = await self.create_and_initialize(
            component_class=component_class,
            name=name,
            application_context=application_context,
            component_config=component_config,
            executor=executor
        )
        self._log_info(f"ComponentFactory: компонент {name} успешно создан")
        return result
