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
        component_config: ComponentConfig
    ) -> BaseComponent:
        """
        Создание и инициализация компонента с автоматической загрузкой ресурсов.

        ARGS:
        - component_class: класс компонента для создания
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента

        RETURNS:
        - BaseComponent: созданный и инициализированный компонент
        """
        self.logger.info(f"Создание компонента {name} типа {component_class.__name__}")

        # Создание экземпляра компонента
        component = component_class(
            name=name,
            application_context=application_context,
            component_config=component_config
        )

        # Инициализация компонента (загрузка промптов и контрактов в кэш)
        init_success = await component.initialize()

        if not init_success:
            self.logger.warning(f"Компонент {name} не смог полностью инициализироваться, но продолжает работу")
        else:
            self.logger.info(f"Компонент {name} успешно инициализирован")

        # Проверка, что компонент действительно инициализирован
        if not component._initialized:
            self.logger.warning(f"Компонент {name} имеет _initialized=False после инициализации")
        else:
            self.logger.debug(f"Компонент {name}: _initialized=True, кэши заполнены")

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
        import importlib

        if component_type == "service":
            if name == "prompt_service":
                from core.application.services.prompt_service_new import PromptService
                return PromptService
            elif name == "contract_service":
                from core.application.services.contract_service_new import ContractService
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
                    return getattr(module, class_name)
                except ImportError:
                    # Попробуем другой вариант имени модуля
                    try:
                        module_name = f"core.application.services.{name}"
                        class_name = f"{name.title().replace('_', '')}Service"
                        module = __import__(module_name, fromlist=[class_name])
                        return getattr(module, class_name)
                    except ImportError:
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
                return getattr(module, class_name)
            except ImportError:
                # Fallback на старый формат
                try:
                    module_name = f"core.application.skills.{name}_skill"
                    module = importlib.import_module(module_name)
                    class_name = f"{name.title().replace('_', '').replace(' ', '')}Skill"
                    return getattr(module, class_name)
                except ImportError:
                    raise ValueError(f"Навык {name} не найден в core.application.skills.{name}.skill или core.application.skills.{name}_skill")
        elif component_type == "tool":
            # Проверяем специфичные инструменты
            if name == "sql_tool":
                from core.application.tools.sql_tool import SQLTool
                return SQLTool
            elif name == "file_tool":
                from core.application.tools.file_tool import FileTool
                return FileTool
            else:
                # Попробуем стандартный путь
                module_name = f"core.application.tools.{name}_tool"
                class_name = f"{name.title().replace('_', '')}Tool"
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    return getattr(module, class_name)
                except ImportError:
                    # Попробуем другой вариант имени модуля
                    try:
                        module_name = f"core.application.tools.{name}"
                        class_name = f"{name.title().replace('_', '')}Tool"
                        module = __import__(module_name, fromlist=[class_name])
                        return getattr(module, class_name)
                    except ImportError:
                        raise ValueError(f"Инструмент {name} не найден")
            try:
                module = __import__(module_name, fromlist=[class_name])
                return getattr(module, class_name)
            except ImportError:
                raise ValueError(f"Компонент {name} не найден")
        else:
            raise ValueError(f"Неизвестный тип компонента: {component_type}")

    async def create_by_name(
        self,
        component_type: str,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig
    ) -> BaseComponent:
        """
        Создание компонента по имени и типу.

        ARGS:
        - component_type: тип компонента ('skill', 'tool', 'service', 'behavior')
        - name: имя компонента
        - application_context: контекст приложения
        - component_config: конфигурация компонента

        RETURNS:
        - BaseComponent: созданный и инициализированный компонент
        """
        component_class = self._resolve_component_class(component_type, name)
        return await self.create_and_initialize(
            component_class=component_class,
            name=name,
            application_context=application_context,
            component_config=component_config
        )