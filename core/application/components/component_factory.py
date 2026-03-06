"""
Фабрика компонентов - создание и инициализация компонентов с внедрением зависимостей.

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
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent
from core.application.context.application_context import ApplicationContext
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging import EventBusLogger


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
        self._init_event_bus_logger()
    
    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger."""
        if self._infrastructure_context and self._infrastructure_context.event_bus:
            self.event_bus_logger = EventBusLogger(
                self._infrastructure_context.event_bus,
                session_id="system",
                agent_id="system",
                component="ComponentFactory"
            )

    async def _log_info(self, message: str, *args, **kwargs):
        """Информационное сообщение."""
        if self.event_bus_logger:
            await self.event_bus_logger.info(message, *args, **kwargs)

    async def _log_error(self, message: str, *args, **kwargs):
        """Ошибка."""
        if self.event_bus_logger:
            await self.event_bus_logger.error(message, *args, **kwargs)

    def _get_providers(self) -> dict:
        """
        Получить все провайдеры из инфраструктурного контекста.
        
        RETURNS:
        - dict: Словарь с провайдерами по именам
        """
        providers = {}
        infra = self._infrastructure_context
        
        # Получаем провайдеры через фабрики
        if hasattr(infra, 'db_provider_factory') and infra.db_provider_factory:
            providers['db'] = infra.db_provider_factory.get_provider("default_db")
        
        if hasattr(infra, 'llm_provider_factory') and infra.llm_provider_factory:
            providers['llm'] = infra.llm_provider_factory.get_provider("default_llm")
        
        # Vector провайдеры
        if hasattr(infra, '_faiss_providers'):
            providers['vector'] = infra._faiss_providers.get("default_vector")
        
        # Кэш - используем MemoryCacheProvider
        if hasattr(infra, 'cache_provider'):
            providers['cache'] = infra.cache_provider
        
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
        
        АРХИТЕКТУРА:
        1. Получаем провайдеры из InfrastructureContext
        2. Передаём их в конструктор компонента как интерфейсы
        3. Компонент не зависит от контекстов напрямую
        
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
        
        # 1. Получаем провайдеры из инфраструктурного контекста
        providers = self._get_providers()
        
        await self._log_info(
            f"Получены провайдеры для {name}: " +
            ", ".join([k for k, v in providers.items() if v is not None])
        )
        
        # 2. Анализируем сигнатуру конструктора компонента
        import inspect
        sig = inspect.signature(component_class.__init__)
        params = sig.parameters
        
        # 3. Формируем аргументы для конструктора
        kwargs = {
            'name': name,
            'component_config': component_config,
            'executor': executor
        }
        
        # 4. Передаем провайдеры как интерфейсы
        # Если компонент принимает application_context - передаём (для обратной совместимости)
        if 'application_context' in params:
            kwargs['application_context'] = application_context
        
        # Передаем провайдеры по именам параметров
        if 'db' in params and providers.get('db'):
            kwargs['db'] = providers['db']
        
        if 'llm' in params and providers.get('llm'):
            kwargs['llm'] = providers['llm']
        
        if 'cache' in params and providers.get('cache'):
            kwargs['cache'] = providers['cache']
        
        if 'vector' in params and providers.get('vector'):
            kwargs['vector'] = providers['vector']
        
        if 'event_bus' in params and providers.get('event_bus'):
            kwargs['event_bus'] = providers['event_bus']
        
        if 'prompt_storage' in params and providers.get('prompt_storage'):
            kwargs['prompt_storage'] = providers['prompt_storage']
        
        if 'contract_storage' in params and providers.get('contract_storage'):
            kwargs['contract_storage'] = providers['contract_storage']
        
        if 'metrics_storage' in params and providers.get('metrics_storage'):
            kwargs['metrics_storage'] = providers['metrics_storage']
        
        if 'log_storage' in params and providers.get('log_storage'):
            kwargs['log_storage'] = providers['log_storage']
        
        # 5. Специальная обработка для behavior patterns
        from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
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
        Разрешение класса компонента по имени и типу.
        
        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента
        
        RETURNS:
        - Type[BaseComponent]: класс компонента
        """
        await self._log_info(f"Разрешение класса компонента: тип={component_type}, имя={name}")
        
        import importlib
        
        if component_type == "service":
            await self._log_info(f"Поиск сервиса: {name}")
            if name == "prompt_service":
                await self._log_info("Найден PromptService")
                from core.application.services.prompt_service import PromptService
                return PromptService
            elif name == "contract_service":
                await self._log_info("Найден ContractService")
                from core.application.services.contract_service import ContractService
                return ContractService
            elif name == "table_description_service":
                from core.application.services.table_description_service import TableDescriptionService
                return TableDescriptionService
            elif name == "sql_generation":
                from core.application.services.sql_generation.service import SQLGenerationService
                return SQLGenerationService
            elif name == "sql_query_service":
                from core.application.services.sql_query.service import SQLQueryService
                return SQLQueryService
            elif name == "sql_validator_service":
                from core.application.services.sql_validator.service import SQLValidatorService
                return SQLValidatorService
            else:
                # Попробуем динамический импорт
                module_name = f"core.application.services.{name.replace('_', '')}_service"
                class_name = f"{name.title().replace('_', '')}Service"
                try:
                    module = importlib.import_module(module_name)
                    result = getattr(module, class_name)
                    await self._log_info(f"Динамически найден сервис: {result}")
                    return result
                except ImportError:
                    await self._log_error(f"Сервис {name} не найден")
                    raise ValueError(f"Сервис {name} не найден")
                    
        elif component_type == "skill":
            # Поддержка ОБОИХ вариантов структуры
            try:
                # Сначала пробуем поддиректорию (реальная структура)
                module_name = f"core.application.skills.{name}.skill"
                class_name = f"{name.title().replace('_', '').replace(' ', '')}Skill"
                module = importlib.import_module(module_name)
                result = getattr(module, class_name)
                await self._log_info(f"Найден навык: {result}")
                return result
            except ImportError:
                # Fallback на старый формат
                try:
                    module_name = f"core.application.skills.{name}_skill"
                    module = importlib.import_module(module_name)
                    class_name = f"{name.title().replace('_', '').replace(' ', '')}Skill"
                    result = getattr(module, class_name)
                    await self._log_info(f"Найден навык (старый формат): {result}")
                    return result
                except ImportError:
                    await self._log_error(f"Навык {name} не найден")
                    raise ValueError(f"Навык {name} не найден")
                    
        elif component_type == "tool":
            # Проверяем специфичные инструменты
            if name == "sql_tool":
                from core.application.tools.sql_tool import SQLTool
                return SQLTool
            elif name == "file_tool":
                from core.application.tools.file_tool import FileTool
                return FileTool
            elif name == "vector_books_tool":
                from core.application.tools.vector_books_tool import VectorBooksTool
                return VectorBooksTool
            elif name == "book_library":
                from core.application.skills.book_library.skill import BookLibrarySkill
                return BookLibrarySkill
            else:
                # Попробуем стандартный путь
                module_name = f"core.application.tools.{name}_tool"
                class_name = f"{name.title().replace('_', '')}Tool"
                try:
                    module = importlib.import_module(module_name)
                    result = getattr(module, class_name)
                    await self._log_info(f"Найден инструмент: {result}")
                    return result
                except ImportError:
                    await self._log_error(f"Инструмент {name} не найден")
                    raise ValueError(f"Инструмент {name} не найден")
                    
        elif component_type == "behavior":
            # Обработка паттернов поведения
            if name == "react_pattern":
                from core.application.behaviors.react.pattern import ReActPattern
                return ReActPattern
            elif name == "planning_pattern":
                from core.application.behaviors.planning.pattern import PlanningPattern
                return PlanningPattern
            elif name == "fallback_pattern":
                from core.application.behaviors.fallback.pattern import FallbackPattern
                return FallbackPattern
            elif name == "evaluation_pattern":
                from core.application.behaviors.evaluation.pattern import EvaluationPattern
                return EvaluationPattern
            else:
                # Попробуем стандартный путь
                module_name = f"core.application.behaviors.{name}_pattern"
                class_name = f"{name.title().replace('_', '')}Pattern"
                try:
                    module = importlib.import_module(module_name)
                    result = getattr(module, class_name)
                    await self._log_info(f"Найден паттерн поведения: {result}")
                    return result
                except ImportError:
                    await self._log_error(f"Паттерн поведения {name} не найден")
                    raise ValueError(f"Паттерн поведения {name} не найден")
        else:
            await self._log_error(f"Неизвестный тип компонента: {component_type}")
            raise ValueError(f"Неизвестный тип компонента: {component_type}")

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
