"""
Прикладной контекст - версионируемый контекст для сессии/агента.

СОДЕРЖИТ:
- Изолированные кэши: промптов, контрактов
- Навыки с изолированными кэшами
- Сессионные сервисы (при необходимости)
- Конфигурацию: AppConfig, флаги (side_effects_enabled, detailed_metrics)
- Ссылку на InfrastructureContext (только для чтения)
"""
import uuid
import logging
from typing import Dict, Optional, Any, Literal
from datetime import datetime
from enum import Enum

from core.application.components.tool import BaseTool
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.skills.base_skill import BaseSkill
from core.application.services.prompt_service_new import PromptService
from core.application.services.contract_service_new import ContractService
from core.application.context.base_system_context import BaseSystemContext


class ComponentType(Enum):
    """Типы компонентов прикладного уровня"""
    SERVICE = "service"      # PromptService, ContractService
    SKILL = "skill"          # PlanningSkill, BookLibrarySkill
    TOOL = "tool"            # SQLTool, FileTool
    STRATEGY = "strategy"    # ReActStrategy, PlanAndExecuteStrategy


class ComponentRegistry:
    """Единый реестр ВСЕХ компонентов прикладного контекста"""
    
    def __init__(self):
        # {component_type: {component_name: component_instance}}
        self._components: Dict[ComponentType, Dict[str, 'BaseComponent']] = {
            t: {} for t in ComponentType
        }
    
    def register(self, component_type: ComponentType, name: str, component: 'BaseComponent'):
        if name in self._components[component_type]:
            raise ValueError(f"Компонент {component_type.value}.{name} уже зарегистрирован")
        self._components[component_type][name] = component
    
    def get(self, component_type: ComponentType, name: str) -> Optional['BaseComponent']:
        return self._components[component_type].get(name)
    
    def all_of_type(self, component_type: ComponentType) -> list['BaseComponent']:
        return list(self._components[component_type].values())
    
    def all_components(self) -> list['BaseComponent']:
        return [comp for comps in self._components.values() for comp in comps.values()]


class ApplicationContext(BaseSystemContext):
    """Версионируемый контекст приложения. Создаётся на сессию/агента."""

    def __init__(
        self,
        infrastructure_context: InfrastructureContext,
        config: 'AppConfig',  # Единая конфигурация приложения
        profile: Literal["prod", "sandbox"] = "prod"  # Профиль работы
    ):
        """
        Инициализация прикладного контекста.

        ПАРАМЕТРЫ:
        - infrastructure_context: Инфраструктурный контекст (только для чтения!)
        - config: Единая конфигурация приложения (AppConfig)
        - profile: Профиль работы ('prod' или 'sandbox')
        """
        self.id = str(uuid.uuid4())
        self.infrastructure_context = infrastructure_context  # Только для чтения!
        self.config = config
        self.profile = profile  # "prod" или "sandbox"
        self._prompt_overrides: Dict[str, str] = {}  # Только для песочницы
        self._initialized = False  # Защита от раннего доступа

        # ЕДИНСТВЕННОЕ место хранения всех компонентов
        self.components = ComponentRegistry()

        # Флаги конфигурации из AppConfig
        self.side_effects_enabled = getattr(config, 'side_effects_enabled', True)
        self.detailed_metrics = getattr(config, 'detailed_metrics', False)

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.id}")

    def _resolve_component_configs(self) -> Dict[ComponentType, Dict[str, Any]]:
        """
        ЕДИНЫЙ источник конфигурации для всех компонентов.
        Конфигурация берётся из ЕДИНСТВЕННОГО источника — AppConfig.
        """
        # Используем getattr с пустым словарем по умолчанию для безопасности
        service_configs = getattr(self.config, 'service_configs', {})
        skill_configs = getattr(self.config, 'skill_configs', {})
        tool_configs = getattr(self.config, 'tool_configs', {})
        strategy_configs = getattr(self.config, 'strategy_configs', {})
        
        self.logger.debug(f"Загружено конфигураций: services={len(service_configs)}, skills={len(skill_configs)}, tools={len(tool_configs)}, strategies={len(strategy_configs)}")
        
        return {
            ComponentType.SERVICE: service_configs,
            ComponentType.SKILL: skill_configs,
            ComponentType.TOOL: tool_configs,
            ComponentType.STRATEGY: strategy_configs,
        }

    def _resolve_component_class(self, component_type: ComponentType, name: str) -> type:
        """Разрешение класса компонента по имени и типу (через фабрику или реестр)"""
        import importlib
        
        # Временная реализация - в реальном проекте должна быть фабрика компонентов
        if component_type == ComponentType.SERVICE:
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
        elif component_type == ComponentType.SKILL:
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
        elif component_type == ComponentType.TOOL:
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
        elif component_type == ComponentType.STRATEGY:
            module_name = f"core.application.strategies.{name}_strategy"
            class_name = f"{name.title().replace('_', '')}Strategy"
            try:
                module = __import__(module_name, fromlist=[class_name])
                return getattr(module, class_name)
            except ImportError:
                raise ValueError(f"Стратегия {name} не найдена")
        else:
            raise ValueError(f"Неизвестный тип компонента: {component_type}")

    async def _create_component(self, component_type: ComponentType, name: str, config: Any) -> 'BaseComponent':
        """
        ЕДИНЫЙ фабричный метод для создания ЛЮБОГО компонента.
        Устраняет дублирование логики между _create_services/_create_skills/_create_tools
        """
        # 1. Получение класса компонента по имени и типу
        component_class = self._resolve_component_class(component_type, name)

        # 2. Создание экземпляра с ЕДИНЫМ контрактом конструктора
        # Правильно различаем AppConfig и ComponentConfig
        try:
            # Если config является ComponentConfig (локальная конфигурация компонента), 
            # передаем его как component_config
            from core.config.component_config import ComponentConfig
            if isinstance(config, ComponentConfig):
                component = component_class(
                    name=name,
                    application_context=self,
                    component_config=config  # передаем ComponentConfig как component_config
                )
            else:
                # Если config - это AppConfig или другой тип, передаем как app_config
                component = component_class(
                    name=name,
                    application_context=self,
                    app_config=config
                )
        except TypeError:
            # Если компонент не принимает component_config или app_config, пробуем оба варианта
            try:
                # Пробуем передать config как component_config (если это ComponentConfig)
                from core.config.component_config import ComponentConfig
                if isinstance(config, ComponentConfig):
                    component = component_class(
                        name=name,
                        application_context=self,
                        component_config=config
                    )
                else:
                    # Если config не ComponentConfig, создаем минимальный ComponentConfig
                    minimal_config = ComponentConfig(
                        variant_id=f"{name}_default",
                        prompt_versions={},
                        input_contract_versions={},
                        output_contract_versions={},
                        side_effects_enabled=getattr(self.config, 'side_effects_enabled', True),
                        detailed_metrics=getattr(self.config, 'detailed_metrics', False)
                    )
                    component = component_class(
                        name=name,
                        application_context=self,
                        component_config=minimal_config
                    )
            except TypeError:
                # Если ничего не работает, создаем с минимальными параметрами
                from core.config.component_config import ComponentConfig
                # Создаем минимальный ComponentConfig для случая, когда конфигурация отсутствует
                if config is None:
                    config = ComponentConfig(
                        variant_id=f"{name}_default",
                        prompt_versions={},
                        input_contract_versions={},
                        output_contract_versions={},
                        side_effects_enabled=getattr(self.config, 'side_effects_enabled', True),
                        detailed_metrics=getattr(self.config, 'detailed_metrics', False)
                    )
                
                # Создаем экземпляр и вызываем инициализацию вручную
                component = component_class.__new__(component_class)
                
                # Устанавливаем основные атрибуты
                component.name = name
                component.application_context = self
                
                # Пытаемся вызвать инициализацию с подходящим параметром конфигурации
                # Сначала пробуем component_config (для нового архитектурного подхода)
                try:
                    component.__init__(name=name, application_context=self, component_config=config)
                except TypeError:
                    # Затем пробуем app_config (для обратной совместимости)
                    try:
                        component.__init__(name=name, application_context=self, app_config=config)
                    except TypeError:
                        # Если оба варианта не работают, используем минимальную конфигурацию
                        minimal_config = ComponentConfig(
                            variant_id=f"{name}_default",
                            prompt_versions={},
                            input_contract_versions={},
                            output_contract_versions={},
                            side_effects_enabled=getattr(self.config, 'side_effects_enabled', True),
                            detailed_metrics=getattr(self.config, 'detailed_metrics', False)
                        )
                        component.__init__(name=name, application_context=self, component_config=minimal_config)

        return component

    async def initialize(self) -> bool:
        """
        ЕДИНЫЙ жизненный цикл инициализации для ВСЕХ компонентов:
        1. Создание и регистрация → 2. Инициализация с учетом зависимостей → 3. Валидация
        """
        if self._initialized:
            self.logger.warning("ApplicationContext уже инициализирован")
            return True

        self.logger.info(f"Начало инициализации ApplicationContext {self.id}")

        # === ЭТАП 1: Создание и регистрация ВСЕХ компонентов (без инициализации) ===
        component_configs = self._resolve_component_configs()
        
        # Сначала создаем и регистрируем все компоненты
        for comp_type, configs in component_configs.items():
            for name, config in configs.items():
                try:
                    # ЕДИНЫЙ метод создания любого компонента
                    component = await self._create_component(comp_type, name, config)
                    
                    # Регистрация компонента ДО инициализации
                    self.components.register(comp_type, name, component)
                    
                    self.logger.debug(f"Компонент {comp_type.value}.{name} зарегистрирован")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка создания {comp_type.value}.{name}: {e}")
                    return False

        # === ЭТАП 2: Инициализация компонентов с учетом зависимостей ===
        # Инициализируем компоненты в правильном порядке
        success = await self._initialize_components_with_dependencies()
        if not success:
            self.logger.error("Ошибка инициализации компонентов с учетом зависимостей")
            return False

        # === ЭТАП 3: Валидация готовности системы ===
        if not await self._verify_readiness():
            return False

        self._initialized = True
        self.logger.info(f"ApplicationContext {self.id} успешно инициализирован")

        return True

    async def _initialize_components_with_dependencies(self) -> bool:
        """
        Инициализация компонентов с учетом зависимостей.
        Инициализирует сначала сервисы, затем инструменты, навыки и стратегии.
        """
        from core.application.context.application_context import ComponentType

        # Получаем все компоненты и группируем по типам
        all_components = self.components.all_components()
        
        # Разделяем компоненты по типам для инициализации в правильном порядке
        services = []
        tools = []
        skills = []
        strategies = []
        
        for component in all_components:
            # Определяем тип компонента по его положению в реестре
            found = False
            for comp_type in self.components._components:
                if component.name in self.components._components[comp_type]:
                    if comp_type == ComponentType.SERVICE:
                        services.append(component)
                    elif comp_type == ComponentType.TOOL:
                        tools.append(component)
                    elif comp_type == ComponentType.SKILL:
                        skills.append(component)
                    elif comp_type == ComponentType.STRATEGY:
                        strategies.append(component)
                    found = True
                    break
            
            if not found:
                # Если тип не найден, добавляем в общий список
                services.append(component)  # по умолчанию
        
        # Инициализируем компоненты в правильном порядке:
        # 1. Сервисы (они нужны инструментам и другим компонентам)
        # 2. Инструменты, навыки, стратегии (они могут зависеть от сервисов)
        
        initialized_components = set()
        
        # Сначала инициализируем сервисы
        self.logger.info(f"Инициализация сервисов: {len(services)}")
        for component in services:
            try:
                if hasattr(component, 'initialize') and callable(component.initialize):
                    if await component.initialize():
                        initialized_components.add(component.name)
                        self.logger.debug(f"Сервис {component.name} инициализирован")
                    else:
                        self.logger.error(f"Сервис {component.name} не смог инициализироваться")
                        return False
                else:
                    initialized_components.add(component.name)
                    self.logger.debug(f"Сервис {component.name} не требует инициализации")
            except Exception as e:
                self.logger.error(f"Ошибка при инициализации сервиса {component.name}: {e}")
                return False
        
        # Затем инициализируем инструменты, навыки и стратегии
        other_components = tools + skills + strategies
        self.logger.info(f"Инициализация других компонентов: {len(other_components)}")
        
        for component in other_components:
            try:
                if hasattr(component, 'initialize') and callable(component.initialize):
                    if await component.initialize():
                        initialized_components.add(component.name)
                        self.logger.debug(f"Компонент {component.name} инициализирован")
                    else:
                        self.logger.warning(f"Компонент {component.name} не смог инициализироваться")
                        # Не возвращаем False, так как это может быть не критично
                else:
                    initialized_components.add(component.name)
                    self.logger.debug(f"Компонент {component.name} не требует инициализации")
            except Exception as e:
                self.logger.warning(f"Ошибка при инициализации компонента {component.name}: {e}")
                # Не возвращаем False, так как это может быть не критично для инструментов
        
        # Проверяем, все ли компоненты были инициализированы
        all_names = {comp.name for comp in all_components}
        if len(initialized_components) != len(all_names):
            uninitialized = all_names - initialized_components
            self.logger.warning(f"Не все компоненты были инициализированы: {uninitialized}")
            # Возвращаем True, если инициализированы все сервисы, так как они наиболее важны
            service_names = {s.name for s in services}
            initialized_services = service_names.intersection(initialized_components)
            if len(initialized_services) != len(service_names):
                self.logger.error("Не все сервисы были инициализированы")
                return False
        
        self.logger.info(f"Компоненты успешно инициализированы (сервисы: {len(services)}, другие: {len(other_components)})")
        return True

    async def _verify_readiness(self) -> bool:
        """Валидация, что ВСЕ компоненты готовы к работе"""
        # Проверка, что все компоненты, которые были объявлены в конфигурации, инициализированы
        
        # Получаем все компоненты, которые должны быть загружены
        declared_components = self._resolve_component_configs()
        
        for comp_type, names in declared_components.items():
            for name in names:
                component = self.components.get(comp_type, name)
                if component is None:
                    self.logger.error(f"Компонент {comp_type.value}.{name} был объявлен в конфигурации, но не загружен")
                    return False
                # Проверяем, что компонент инициализирован
                if hasattr(component, '_initialized'):
                    if not component._initialized:
                        self.logger.error(f"Компонент {comp_type.value}.{name} не инициализирован")
                        return False
                elif hasattr(component, 'is_ready') and callable(component.is_ready):
                    if not component.is_ready():
                        self.logger.error(f"Компонент {component.name} не готов к работе")
                        return False
        
        return True

    # === ЕДИНЫЕ точки доступа к компонентам ===
    
    def get_service(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.SERVICE, name)
    
    def get_skill(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.SKILL, name)
    
    def get_tool(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.TOOL, name)
    
    def get_strategy(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.STRATEGY, name)

    async def _validate_versions_by_profile(self, prompt_versions: dict, input_contract_versions: dict = None, output_contract_versions: dict = None) -> bool:
        """Валидация статусов версий в зависимости от профиля"""
        # Валидация промптов
        if prompt_versions:
            try:
                prompt_repository = self.infrastructure_context.get_prompt_storage()
                
                for capability, version in prompt_versions.items():
                    try:
                        # Проверяем существование файла версии через хранилище
                        exists = await prompt_repository.exists(capability, version)
                        if not exists:
                            self.logger.error(
                                f"[{self.profile.upper()}] Промпт версия {capability}@{version} не существует. Отклонено."
                            )
                            return False
                        
                        # Загружаем через хранилище, чтобы получить правильный объект Prompt
                        prompt_obj = await prompt_repository.load(capability, version)
                        
                        # Получаем статус из метаданных объекта Prompt
                        if hasattr(prompt_obj, 'metadata') and hasattr(prompt_obj.metadata, 'status'):
                            # Если status - это enum, получаем его значение
                            status_obj = prompt_obj.metadata.status
                            if hasattr(status_obj, 'value'):
                                status = status_obj.value
                            else:
                                # Если status уже строка
                                status = str(status_obj)
                        else:
                            self.logger.warning(
                                f"Не удалось получить статус для промпта {capability}@{version}, используем 'draft'"
                            )
                            status = 'draft'
                        
                        if self.profile == "prod":
                            # В продакшне ТОЛЬКО активные версии
                            if status != "active":
                                self.logger.error(
                                    f"[PROD] Промпт версия {capability}@{version} имеет статус '{status}', "
                                    f"но требуется 'active'. Отклонено."
                                )
                                return False
                        
                        elif self.profile == "sandbox":
                            # В песочнице разрешены draft + active (но не archived)
                            if status == "archived":
                                self.logger.warning(
                                    f"[SANDBOX] Промпт версия {capability}@{version} архивирована"
                                )
                    except Exception as e:
                        self.logger.error(
                            f"Не удалось загрузить или получить статус для промпта {capability}@{version}: {e}. "
                            f"Отклонено для профиля {self.profile}."
                        )
                        # Если не удалось прочитать статус, в песочнице разрешаем, в проде - нет
                        if self.profile == "prod":
                            return False
            except Exception as e:
                self.logger.error(f"Ошибка при доступе к хранилищу промптов: {e}")
                return False

        # Валидация входных контрактов
        if input_contract_versions:
            try:
                contract_repository = self.infrastructure_context.get_contract_storage()
                
                for capability, version in input_contract_versions.items():
                    try:
                        # Проверяем существование файла версии через хранилище
                        exists = await contract_repository.exists(capability, version, "input")
                        if not exists:
                            self.logger.error(
                                f"[{self.profile.upper()}] Входной контракт версия {capability}@{version} не существует. Отклонено."
                            )
                            return False
                        
                        # Загружаем через хранилище, чтобы получить правильный объект Contract
                        contract_obj = await contract_repository.load(capability, version, "input")
                        
                        # Для контрактов пока не проверяем статус, но можно добавить в будущем
                        # В продакшне можно добавить проверки на соответствие определенным критериям
                        
                    except Exception as e:
                        self.logger.error(
                            f"Не удалось загрузить входной контракт {capability}@{version}: {e}. "
                            f"Отклонено для профиля {self.profile}."
                        )
                        # Если не удалось загрузить контракт, в проде - не разрешаем
                        if self.profile == "prod":
                            return False
            except Exception:
                # Если хранилище контрактов не существует или недоступно, пропускаем валидацию
                self.logger.warning("Хранилище контрактов недоступно, пропускаем валидацию входных контрактов")
                pass

        # Валидация выходных контрактов
        if output_contract_versions:
            try:
                contract_repository = self.infrastructure_context.get_contract_storage()
                
                for capability, version in output_contract_versions.items():
                    try:
                        # Проверяем существование файла версии через хранилище
                        exists = await contract_repository.exists(capability, version, "output")
                        if not exists:
                            self.logger.error(
                                f"[{self.profile.upper()}] Выходной контракт версия {capability}@{version} не существует. Отклонено."
                            )
                            return False
                        
                        # Загружаем через хранилище, чтобы получить правильный объект Contract
                        contract_obj = await contract_repository.load(capability, version, "output")
                        
                        # Для контрактов пока не проверяем статус, но можно добавить в будущем
                        
                    except Exception as e:
                        self.logger.error(
                            f"Не удалось загрузить выходной контракт {capability}@{version}: {e}. "
                            f"Отклонено для профиля {self.profile}."
                        )
                        # Если не удалось загрузить контракт, в проде - не разрешаем
                        if self.profile == "prod":
                            return False
            except Exception:
                # Если хранилище контрактов не существует или недоступно, пропускаем валидацию
                self.logger.warning("Хранилище контрактов недоступно, пропускаем валидацию выходных контрактов")
                pass

        return True

    @classmethod
    async def create_prod_auto(cls, infrastructure_context, profile="prod"):
        """
        Создание продакшен контекста с автоматически сгенерированной конфигурацией.
        Автоматически находит все активные версии промптов и контрактов.
        """
        from core.config.app_config import AppConfig
        
        # Создаем минимальную конфигурацию, которая будет заполнена автоматически
        empty_config = AppConfig(config_id=f"auto_prod_{infrastructure_context.id[:8]}")
        
        # Создаём контекст с минимальной конфигурацией
        context = cls(
            infrastructure_context=infrastructure_context,
            config=empty_config,
            profile=profile
        )
        
        # Автоматически заполняем конфигурацию активными версиями
        await context._auto_fill_config()
        
        return context
    
    async def _auto_fill_config(self):
        """
        Автоматическое заполнение конфигурации активными версиями промптов и контрактов.
        Используется для продакшена, когда конфигурация не указана явно.
        """
        # Получаем хранилища
        prompt_storage = self.infrastructure_context.get_prompt_storage()
        contract_storage = self.infrastructure_context.get_contract_storage()
        
        # Сканируем активные версии промптов
        active_prompts = {}
        active_input_contracts = {}
        active_output_contracts = {}
        
        # Сканируем директории промптов для определения доступных capability
        from pathlib import Path
        
        prompts_dir = Path(prompt_storage.prompts_dir)
        if prompts_dir.exists():
            for capability_dir in prompts_dir.iterdir():
                if capability_dir.is_dir():
                    capability = capability_dir.name
                    # Ищем файлы версий в этой директории
                    for file_path in capability_dir.glob("*.yaml"):
                        version = file_path.stem  # имя файла без расширения
                        
                        try:
                            # Загружаем промпт и проверяем статус
                            prompt_obj = await prompt_storage.load(capability, version)
                            if hasattr(prompt_obj, 'metadata') and hasattr(prompt_obj.metadata, 'status'):
                                status = prompt_obj.metadata.status.value
                                if status == "active":
                                    active_prompts[capability] = version
                        except Exception:
                            # Если не удалось загрузить или проверить статус, пропускаем
                            continue
        
        # Сканируем директории контрактов для определения доступных capability
        contracts_dir = Path(contract_storage.contracts_dir)
        if contracts_dir.exists():
            for category_dir in contracts_dir.iterdir():
                if category_dir.is_dir():
                    for capability_dir in category_dir.iterdir():
                        if capability_dir.is_dir():
                            capability = capability_dir.name
                            
                            # Проверяем входные контракты
                            for file_path in capability_dir.glob("*_input_*.yaml"):
                                parts = file_path.stem.split('_')
                                if len(parts) >= 3 and parts[-2] == 'input':
                                    version = '_'.join(parts[:-2])  # версия до '_input_'
                                    
                                    try:
                                        contract_obj = await contract_storage.load(capability, version, "input")
                                        # Для контрактов пока просто добавляем, если файл существует
                                        # В будущем можно добавить проверку статуса
                                        active_input_contracts[capability] = version
                                    except Exception:
                                        continue
                            
                            # Проверяем выходные контракты
                            for file_path in capability_dir.glob("*_output_*.yaml"):
                                parts = file_path.stem.split('_')
                                if len(parts) >= 3 and parts[-2] == 'output':
                                    version = '_'.join(parts[:-2])  # версия до '_output_'
                                    
                                    try:
                                        contract_obj = await contract_storage.load(capability, version, "output")
                                        # Для контрактов пока просто добавляем, если файл существует
                                        active_output_contracts[capability] = version
                                    except Exception:
                                        continue
        
        # Создаем новую конфигурацию с активными версиями
        from core.config.app_config import AppConfig
        
        new_config = AppConfig(
            config_id=f"auto_generated_{self.id[:8]}",
            prompt_versions=active_prompts,
            input_contract_versions=active_input_contracts,
            output_contract_versions=active_output_contracts,
            side_effects_enabled=getattr(self.config, 'side_effects_enabled', True),
            detailed_metrics=getattr(self.config, 'detailed_metrics', False),
            max_steps=getattr(self.config, 'max_steps', 10),
            max_retries=getattr(self.config, 'max_retries', 3),
            temperature=getattr(self.config, 'temperature', 0.7),
            default_strategy=getattr(self.config, 'default_strategy', 'react'),
            enable_self_reflection=getattr(self.config, 'enable_self_reflection', True),
            enable_context_window_management=getattr(self.config, 'enable_context_window_management', True)
        )
        
        # Заменяем конфигурацию
        self.config = new_config

    def get_prompt_service(self):
        """Получение изолированного сервиса промптов."""
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self.get_service("prompt_service")

    def get_contract_service(self):
        """Получение изолированного сервиса контрактов."""
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self.get_service("contract_service")

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """Получение навыка по имени."""
        return self.components.get(ComponentType.SKILL, skill_name)

    def get_prompt(self, capability_name: str, version: Optional[str] = None) -> str:
        """
        Получение промпта из изолированного кэша.

        ВАЖНО: Защита от раннего доступа (до инициализации).
        """
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        # В новой архитектуре мы получаем промпт из изолированного сервиса
        prompt_service = self.get_service("prompt_service")
        if prompt_service is None:
            raise RuntimeError("PromptService не инициализирован")
        return prompt_service.get_prompt(capability_name)

    def get_input_contract(self, capability_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение входного контракта из изолированного кэша.

        ВАЖНО: Защита от раннего доступа (до инициализации).
        """
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        # В новой архитектуре мы получаем контракт из изолированного сервиса
        contract_service = self.get_service("contract_service")
        if contract_service is None:
            raise RuntimeError("ContractService не инициализирован")
        return contract_service.get_contract(capability_name, "input")

    def get_output_contract(self, capability_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение выходного контракта из изолированного кэша.

        ВАЖНО: Защита от раннего доступа (до инициализации).
        """
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        # В новой архитектуре мы получаем контракт из изолированного сервиса
        contract_service = self.get_service("contract_service")
        if contract_service is None:
            raise RuntimeError("ContractService не инициализирован")
        return contract_service.get_contract(capability_name, "output")

    def get_provider(self, name: str):
        """Получение провайдера через инфраструктурный контекст."""
        return self.infrastructure_context.get_provider(name)

    def get_tool(self, name: str):
        """Получение инструмента через изолированный контекст приложения."""
        return self.components.get(ComponentType.TOOL, name)

    def get_resource(self, name: str):
        """Получение ресурса - возвращает изолированные сервисы или обращается к инфраструктурному контексту."""
        # Возвращаем изолированные сервисы приложения через новый реестр компонентов
        if name == "prompt_service":
            return self.get_service("prompt_service")
        elif name == "contract_service":
            return self.get_service("contract_service")
        else:
            # Проверяем, может быть это имя компонента в новом реестре
            # Сначала ищем среди сервисов
            service = self.components.get(ComponentType.SERVICE, name)
            if service:
                return service
            
            # Затем ищем среди инструментов
            tool = self.components.get(ComponentType.TOOL, name)
            if tool:
                return tool
                
            # Затем ищем среди навыков
            skill = self.components.get(ComponentType.SKILL, name)
            if skill:
                return skill
                
            # Затем ищем среди стратегий
            strategy = self.components.get(ComponentType.STRATEGY, name)
            if strategy:
                return strategy
            
            # Для других ресурсов обращаемся в инфраструктурный контекст
            return self.infrastructure_context.get_resource(name)

    def set_prompt_override(self, capability: str, version: str):
        """Установка оверрайда версии промпта (только для песочницы)"""
        if self.profile != "sandbox":
            raise RuntimeError(
                "Оверрайды версий разрешены ТОЛЬКО в режиме песочницы"
            )
        
        # Проверка существования версии
        import os
        from pathlib import Path
        repository = self.infrastructure_context.get_prompt_storage()
        prompt_path = Path(repository.prompts_dir) / capability / f"{version}.yaml"
        
        if not prompt_path.exists():
            # Проверяем и другие возможные расширения
            prompt_path_json = Path(repository.prompts_dir) / capability / f"{version}.json"
            if not prompt_path_json.exists():
                raise ValueError(f"Версия {capability}@{version} не существует")
        
        self._prompt_overrides[capability] = version
        self.logger.info(f"Установлен оверрайд: {capability}@{version} для песочницы")

    async def clone_with_version_override(
        self,
        prompt_overrides: Optional[Dict[str, str]] = None,
        contract_overrides: Optional[Dict[str, str]] = None
    ) -> 'ApplicationContext':
        """
        Горячее переключение версий через клонирование.

        Создаёт НОВЫЙ изолированный контекст с обновлёнными версиями.
        """
        from copy import deepcopy

        # Копируем конфигурацию
        new_config = deepcopy(self.config)

        # Применяем оверрайды версий промптов
        if prompt_overrides:
            new_config.prompt_versions.update(prompt_overrides)

        # Применяем оверрайды версий контрактов
        if contract_overrides:
            # Обновляем как входные, так и выходные версии контрактов
            new_config.input_contract_versions.update(contract_overrides)
            new_config.output_contract_versions.update(contract_overrides)

        # Создаём новый контекст с ТЕМ ЖЕ инфраструктурным контекстом и тем же профилем
        new_ctx = ApplicationContext(
            infrastructure_context=self.infrastructure_context,  # Общий для всех!
            config=new_config,
            profile=self.profile  # Сохраняем профиль
        )
        await new_ctx.initialize()

        return new_ctx

    @classmethod
    async def create_from_registry(cls, infrastructure_context, profile: Literal["prod", "sandbox"] = "prod"):
        """
        Создание ApplicationContext с автоматической загрузкой конфигурации из реестра.
        
        ARGS:
        - infrastructure_context: инфраструктурный контекст
        - profile: профиль (prod или sandbox)
        
        RETURNS:
        - ApplicationContext: сконфигурированный экземпляр
        """
        app_config = AppConfig.from_registry(profile=profile)
        context = cls(
            infrastructure_context=infrastructure_context,
            config=app_config,
            profile=profile
        )
        await context.initialize()
        return context

    def get_resource(self, name: str):
        """
        Получение ресурса по имени.
        Возвращает изолированные сервисы приложения или обращается к инфраструктурному контексту.
        """
        # Возвращаем изолированные сервисы приложения
        if name == "prompt_service":
            return self.get_service("prompt_service")
        elif name == "contract_service":
            return self.get_service("contract_service")
        else:
            # Для других ресурсов обращаемся в инфраструктурный контекст
            return self.infrastructure_context.get_resource(name)

    def get_service(self, name: str):
        """
        Получение сервиса по имени.
        """
        return self.components.get(ComponentType.SERVICE, name)

    def is_fully_initialized(self) -> bool:
        """
        Проверка, полностью ли инициализирована система.
        """
        return self._initialized