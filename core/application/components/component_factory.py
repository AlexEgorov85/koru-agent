"""
Фабрика компонентов - создание и инициализация компонентов с автоматической загрузкой ресурсов.

СОДЕРЖИТ:
- Создание компонентов с правильной конфигурацией
- Автоматическую инициализацию с загрузкой промптов и контрактов
- Обработку зависимостей между компонентами
"""
import logging
from typing import Type, Any, Optional
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent
from core.application.context.application_context import ApplicationContext


class ComponentFactory:
    """Фабрика для создания и инициализации компонентов."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def create_and_initialize(
        self,
        component_class: Type[BaseComponent],
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: 'ActionExecutor'  # Добавляем ActionExecutor
    ) -> BaseComponent:
        """
        Создание и инициализация компонента с автоматической загрузкой ресурсов.

        ARGS:
        - component_class: класс компонента для создания
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента
        - executor: ActionExecutor для взаимодействия между компонентами

        RETURNS:
        - BaseComponent: созданный и инициализированный компонент
        """
        self.logger.info(f"Создание компонента {name} типа {component_class.__name__}")

        # Создание экземпляра компонента с ActionExecutor
        # Проверяем, какой конструктор использовать в зависимости от класса компонента
        import inspect
        sig = inspect.signature(component_class.__init__)
        params = sig.parameters

        self.logger.info(f"Параметры конструктора {component_class.__name__}: {list(params.keys())}")

        # Специальная обработка для behavior patterns (используют component_name вместо name)
        from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
        if issubclass(component_class, BaseBehaviorPattern):
            self.logger.info(f"Создание behavior pattern {component_class.__name__} с component_name={name}")
            component = component_class(
                component_name=name,
                component_config=component_config,
                application_context=application_context,
                executor=executor
            )
        elif 'executor' in params:
            # Если класс принимает executor, передаем его
            self.logger.info(f"Конструктор {component_class.__name__} принимает executor")
            component = component_class(
                name=name,
                application_context=application_context,
                component_config=component_config,
                executor=executor  # Передаем ActionExecutor
            )
        elif len(params) >= 4:  # self + 3 other params
            # Проверяем, является ли третий параметр app_config или component_config
            param_names = list(params.keys())
            if 'app_config' in param_names:
                self.logger.info(f"Конструктор {component_class.__name__} принимает app_config")
                component = component_class(
                    name=name,
                    application_context=application_context,
                    app_config=component_config,  # Используем app_config для старых компонентов
                    executor=executor  # Передаем executor даже если класс не ожидает его явно
                )
            elif 'component_config' in param_names:
                self.logger.info(f"Конструктор {component_class.__name__} принимает component_config")
                component = component_class(
                    name=name,
                    application_context=application_context,
                    component_config=component_config,
                    executor=executor  # Передаем executor
                )
            else:
                # По умолчанию используем component_config
                self.logger.info(f"Конструктор {component_class.__name__} использует component_config по умолчанию")
                component = component_class(
                    name=name,
                    application_context=application_context,
                    component_config=component_config,
                    executor=executor  # Передаем executor
                )
        else:
            # Для старых классов без executor
            self.logger.info(f"Конструктор {component_class.__name__} не принимает executor")
            component = component_class(
                name=name,
                application_context=application_context,
                component_config=component_config
            )

        self.logger.info(f"Компонент {name} создан (инициализация будет выполнена позже через топологическую сортировку)")

        # НЕ вызываем initialize() здесь! Инициализация будет выполнена в _initialize_components_with_dependencies()
        # Это гарантирует, что все зависимости уже зарегистрированы в контексте

        return component

    def _resolve_component_class(self, component_type: str, name: str) -> Type[BaseComponent]:
        """
        Разрешение класса компонента по имени и типу.

        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента

        RETURNS:
        - Type[BaseComponent]: класс компонента
        """
        self.logger.info(f"Разрешение класса компонента: тип={component_type}, имя={name}")
        
        import importlib

        if component_type == "service":
            self.logger.info(f"Поиск сервиса: {name}")
            if name == "prompt_service":
                self.logger.info("Найден PromptService")
                from core.application.services.prompt_service import PromptService
                return PromptService
            elif name == "contract_service":
                self.logger.info("Найден ContractService")
                from core.application.services.contract_service import ContractService
                return ContractService
            elif name == "table_description_service":
                from core.application.services.table_description_service import TableDescriptionService
                return TableDescriptionService
            elif name == "sql_generation_service":
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
                    module = __import__(module_name, fromlist=[class_name])
                    result = getattr(module, class_name)
                    self.logger.info(f"Динамически найден сервис: {result}")
                    return result
                except ImportError:
                    # Попробуем другой вариант имени модуля
                    try:
                        module_name = f"core.application.services.{name}"
                        class_name = f"{name.title().replace('_', '')}Service"
                        module = __import__(module_name, fromlist=[class_name])
                        result = getattr(module, class_name)
                        self.logger.info(f"Динамически найден сервис (вариант 2): {result}")
                        return result
                    except ImportError:
                        self.logger.error(f"Сервис {name} не найден")
                        raise ValueError(f"Сервис {name} не найден")
        elif component_type == "skill":
            # Поддержка ОБОИХ вариантов структуры:
            # Вариант 1: skills/{name}_skill.py
            # Вариант 2: skills/{name}/skill.py (фактическая структура проекта)
            try:
                # Сначала пробуем поддиректорию (реальная структура)
                module_name = f"core.application.skills.{name}.skill"
                class_name = f"{name.title().replace('_', '').replace(' ', '')}Skill"
                module = importlib.import_module(module_name)
                result = getattr(module, class_name)
                self.logger.info(f"Найден навык: {result}")
                return result
            except ImportError:
                # Fallback на старый формат
                try:
                    module_name = f"core.application.skills.{name}_skill"
                    module = importlib.import_module(module_name)
                    class_name = f"{name.title().replace('_', '').replace(' ', '')}Skill"
                    result = getattr(module, class_name)
                    self.logger.info(f"Найден навык (старый формат): {result}")
                    return result
                except ImportError:
                    self.logger.error(f"Навык {name} не найден в core.application.skills.{name}.skill или core.application.skills.{name}_skill")
                    raise ValueError(f"Навык {name} не найден в core.application.skills.{name}.skill или core.application.skills.{name}_skill")
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
            else:
                # Попробуем стандартный путь
                module_name = f"core.application.tools.{name}_tool"
                class_name = f"{name.title().replace('_', '')}Tool"
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    result = getattr(module, class_name)
                    self.logger.info(f"Найден инструмент: {result}")
                    return result
                except ImportError:
                    # Попробуем другой вариант имени модуля
                    try:
                        module_name = f"core.application.tools.{name}"
                        class_name = f"{name.title().replace('_', '')}Tool"
                        module = __import__(module_name, fromlist=[class_name])
                        result = getattr(module, class_name)
                        self.logger.info(f"Найден инструмент (вариант 2): {result}")
                        return result
                    except ImportError:
                        self.logger.error(f"Инструмент {name} не найден")
                        raise ValueError(f"Инструмент {name} не найден")
        elif component_type == "behavior":
            # Обработка паттернов поведения
            # Проверяем специфичные паттерны поведения
            if name == "react_pattern":
                from core.application.behaviors.react.pattern import ReActPattern
                return ReActPattern
            elif name == "planning_pattern":
                from core.application.behaviors.planning.pattern import PlanningPattern
                return PlanningPattern
            elif name == "fallback_pattern":
                from core.application.behaviors.fallback.pattern import FallbackPattern
                return FallbackPattern
            else:
                # Попробуем стандартный путь для паттернов поведения
                module_name = f"core.application.behaviors.{name}_pattern"
                class_name = f"{name.title().replace('_', '')}Pattern"
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    result = getattr(module, class_name)
                    self.logger.info(f"Найден паттерн поведения: {result}")
                    return result
                except ImportError:
                    # Попробуем другой вариант имени модуля
                    try:
                        module_name = f"core.application.behaviors.{name}.pattern"
                        class_name = f"{name.title().replace('_', '')}Pattern"
                        module = __import__(module_name, fromlist=[class_name])
                        result = getattr(module, class_name)
                        self.logger.info(f"Найден паттерн поведения (вариант 2): {result}")
                        return result
                    except ImportError:
                        self.logger.error(f"Паттерн поведения {name} не найден")
                        raise ValueError(f"Паттерн поведения {name} не найден")
        else:
            self.logger.error(f"Неизвестный тип компонента: {component_type}")
            raise ValueError(f"Неизвестный тип компонента: {component_type}")

    async def create_by_name(
        self,
        component_type: str,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: 'ActionExecutor'  # Добавляем ActionExecutor
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
        self.logger.info(f"ComponentFactory: создание компонента {name} типа {component_type}")
        component_class = self._resolve_component_class(component_type, name)
        self.logger.info(f"ComponentFactory: найден класс {component_class.__name__} для {name}")
        result = await self.create_and_initialize(
            component_class=component_class,
            name=name,
            application_context=application_context,
            component_config=component_config,
            executor=executor  # Передаем ActionExecutor
        )
        self.logger.info(f"ComponentFactory: компонент {name} успешно создан (инициализация будет выполнена позже)")
        return result