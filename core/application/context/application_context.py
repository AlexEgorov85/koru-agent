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
from pathlib import Path
from typing import Dict, Optional, Any, Literal, Type
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from core.application.tools.base_tool import BaseTool
from core.config.app_config import AppConfig
from core.config.registry_loader import RegistryLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.skills.base_skill import BaseSkill
from core.application.services.prompt_service import PromptService
from core.application.services.contract_service import ContractService
from core.application.context.base_system_context import BaseSystemContext
from core.application.data_repository import DataRepository
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource


from core.models.enums.common_enums import ComponentType


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
        profile: Literal["prod", "sandbox"] = "prod",  # Профиль работы
        use_data_repository: bool = True  # По умолчанию ВКЛЮЧЁН (после тестирования)
    ):
        """
        Инициализация прикладного контекста.

        ПАРАМЕТРЫ:
        - infrastructure_context: Инфраструктурный контекст (только для чтения!)
        - config: Единая конфигурация приложения (AppConfig)
        - profile: Профиль работы ('prod' или 'sandbox')
        - use_data_repository: использовать новый DataRepository (по умолчанию True)
        """
        self.id = str(uuid.uuid4())
        self.infrastructure_context = infrastructure_context  # Только для чтения!
        self.config = config
        self.profile = profile  # "prod" или "sandbox"
        self._prompt_overrides: Dict[str, str] = {}  # Только для песочницы
        self._initialized = False  # Защита от раннего доступа
        self.use_data_repository = use_data_repository  # Новый флаг

        # ЕДИНСТВЕННОЕ место хранения всех компонентов
        self.components = ComponentRegistry()

        # Флаги конфигурации из AppConfig
        self.side_effects_enabled = getattr(config, 'side_effects_enabled', True)
        self.detailed_metrics = getattr(config, 'detailed_metrics', False)

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.id}")

        # Создаём репозиторий с явным источником данных
        if use_data_repository:
            # Загружаем реестр напрямую (для получения capability_types)
            registry_loader = RegistryLoader(Path(infrastructure_context.config.data_dir) / "registry.yaml")
            registry_config = registry_loader.load(profile=profile)

            # Создаём источник данных поверх ФС (новая архитектурно-правильная реализация)
            fs_data_source = FileSystemDataSource(
                Path(infrastructure_context.config.data_dir),
                registry_config
            )

            # Инициализируем источник данных (строгая валидация по архитектурным требованиям)
            fs_data_source.initialize()

            # Создаём репозиторий
            self.data_repository = DataRepository(fs_data_source, profile=profile)
        else:
            self.data_repository = None  # ← Старый путь (для отката)

    def _resolve_component_configs(self) -> Dict[ComponentType, Dict[str, Any]]:
        """
        ЕДИНЫЙ источник конфигурации для всех компонентов.
        Конфигурация берётся из ЕДИНСТВЕННОГО источника — AppConfig.
        """
        # Используем getattr с пустым словарем по умолчанию для безопасности
        service_configs = getattr(self.config, 'service_configs', {})
        skill_configs = getattr(self.config, 'skill_configs', {})
        tool_configs = getattr(self.config, 'tool_configs', {})
        behavior_configs = getattr(self.config, 'behavior_configs', {})

        self.logger.debug(f"Загружено конфигураций: services={len(service_configs)}, skills={len(skill_configs)}, tools={len(tool_configs)}, behaviors={len(behavior_configs)}")

        return {
            ComponentType.SERVICE: service_configs,
            ComponentType.SKILL: skill_configs,
            ComponentType.TOOL: tool_configs,
            ComponentType.BEHAVIOR: behavior_configs,
        }

    def _resolve_component_class(self, component_type: ComponentType, name: str) -> type:
        """Разрешение класса компонента по имени и типу (через фабрику или реестр)"""
        # Используем новую фабрику компонентов
        from core.application.components.component_factory import ComponentFactory
        factory = ComponentFactory()
        return factory._resolve_component_class(component_type.value, name)

    async def _create_component(self, component_type: ComponentType, name: str, config: Any, executor: 'ActionExecutor') -> 'BaseComponent':
        """
        ЕДИНЫЙ фабричный метод для создания ЛЮБОГО компонента.
        Устраняет дублирование логики между _create_services/_create_skills/_create_tools
        """
        self.logger.info(f"Начало создания компонента {component_type.value}.{name}")
        
        # Используем новую фабрику компонентов для создания и инициализации
        from core.application.components.component_factory import ComponentFactory
        from core.config.component_config import ComponentConfig

        factory = ComponentFactory()

        # Преобразуем ComponentType в строку для фабрики
        component_type_str = component_type.value

        # Убедимся, что config - это ComponentConfig
        if not isinstance(config, ComponentConfig):
            # Если config не ComponentConfig, создаем минимальный ComponentConfig
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

        self.logger.info(f"Создание компонента {name} типа {component_type_str} с конфигурацией: prompt_versions={list(getattr(config, 'prompt_versions', {}).keys())}, input_contracts={list(getattr(config, 'input_contract_versions', {}).keys())}, output_contracts={list(getattr(config, 'output_contract_versions', {}).keys())}")

        # Создание и инициализация компонента через фабрику
        component = await factory.create_by_name(
            component_type=component_type_str,
            name=name,
            application_context=self,
            component_config=config,
            executor=executor  # Передаем ActionExecutor
        )

        self.logger.info(f"Компонент {component_type.value}.{name} успешно создан фабрикой")

        return component

    async def initialize(self) -> bool:
        """
        ЕДИНЫЙ жизненный цикл инициализации для ВСЕХ компонентов:
        1. Загрузка ВСЕХ промптов/контрактов из хранилищ (один раз!) → 2. Создание и регистрация → 3. Инициализация с учетом зависимостей → 4. Валидация
        """
        if self._initialized:
            self.logger.warning("ApplicationContext уже инициализирован")
            return True

        self.logger.info(f"Начало инициализации ApplicationContext {self.id}")

        # === НОВЫЙ ПУТЬ: Инициализация репозитория с валидацией ===
        if self.use_data_repository and self.data_repository:
            if not await self.data_repository.initialize(self.config):
                self.logger.critical(
                    f"❌ КРИТИЧЕСКАЯ ОШИБКА СТРУКТУРЫ ДАННЫХ:\n"
                    f"{self.data_repository.get_validation_report()}\n"
                    f"Система НЕ БУДЕТ запущена с неконсистентной конфигурацией."
                )
                return False

            self.logger.info(
                f"✅ DataRepository инициализирован успешно:\n"
                f"{self.data_repository.get_validation_report()}"
            )

            # === ЭТАП: Загрузка и валидация манифестов ===
            if self.data_repository:
                await self.data_repository.load_manifests()

                validation_report = await self._validate_manifests_by_profile()

                if validation_report['critical_errors'] and self.profile == "prod":
                    self.logger.critical(
                        f"❌ КРИТИЧЕСКИЕ ОШИБКИ МАНИФЕСТОВ:\n"
                        f"{chr(10).join(validation_report['error_details'])}\n"  # chr(10) = \n
                        f"Система НЕ БУДЕТ запущена с неконсистентными манифестами."
                    )
                    return False

                if validation_report['warnings']:
                    self.logger.warning(
                        f"⚠️ ПРЕДУПРЕЖДЕНИЯ МАНИФЕСТОВ:\n"
                        f"{chr(10).join(validation_report['warning_details'])}"  # chr(10) = \n
                    )

                self.logger.info(
                    f"✅ Валидация манифестов завершена:\n"
                    f"  - Проверено: {validation_report['total_manifests']}\n"
                    f"  - Критических ошибок: {validation_report['critical_errors']}\n"
                    f"  - Предупреждений: {validation_report['warnings']}"
                )

            # === ЭТАП: Валидация дублирования и целостности схем ===
            from core.application.services.manifest_validation_service import ManifestValidationService
            
            validation_service = ManifestValidationService(self.data_repository)
            
            # Валидация дублирования
            duplicate_report = await validation_service.validate_no_duplicates()
            if not duplicate_report['is_valid']:
                self.logger.error(
                    f"❌ ОБНАРУЖЕНО ДУБЛИРОВАНИЕ РЕСУРСОВ:\n"
                    f"- Дубли промптов: {len(duplicate_report['duplicate_prompts'])}\n"
                    f"- Дубли контрактов: {len(duplicate_report['duplicate_contracts'])}\n"
                    f"- Конфликты версий: {len(duplicate_report['version_conflicts'])}"
                )
                if self.profile == "prod":
                    return False
            
            # Валидация целостности схем
            schema_report = await validation_service.validate_schema_integrity()
            if not schema_report['is_valid']:
                self.logger.error(
                    f"❌ НАРУШЕНА ЦЕЛОСТНОСТЬ СХЕМ:\n"
                    f"- Missing input: {len(schema_report['missing_input'])}\n"
                    f"- Missing output: {len(schema_report['missing_output'])}"
                )
                if self.profile == "prod":
                    return False
            
            self.logger.info(
                f"✅ Валидация целостности завершена:\n"
                f"- Дублирование: {'OK' if duplicate_report['is_valid'] else 'FAIL'}\n"
                f"- Целостность схем: {'OK' if schema_report['is_valid'] else 'FAIL'}"
            )

            # Предзагрузка ресурсов в кэши компонентов через репозиторий
            await self._preload_resources_via_repository()

            # === ЭТАП 3: Создание компонентов с предзагруженными ресурсами (НОВЫЙ ПУТЬ) ===
            # Создаем ЕДИНСТВЕННЫЙ экземпляр ActionExecutor для всех компонентов
            from core.application.agent.components.action_executor import ActionExecutor
            executor = ActionExecutor(self)

            # Сначала создаем и регистрируем все компоненты
            component_configs = self._resolve_component_configs()
            for comp_type, configs in component_configs.items():
                for name, enriched_config in configs.items():
                    self.logger.info(f"Создание компонента {comp_type.value}.{name} (новый путь)")
                    try:
                        # ЕДИНЫЙ метод создания любого компонента с ActionExecutor
                        component = await self._create_component(comp_type, name, enriched_config, executor)

                        # Регистрация компонента ДО инициализации
                        self.components.register(comp_type, name, component)

                        self.logger.info(f"Компонент {comp_type.value}.{name} успешно создан и зарегистрирован (новый путь)")

                    except Exception as e:
                        self.logger.error(f"Ошибка создания {comp_type.value}.{name} (новый путь): {e}", exc_info=True)
                        return False

        # === СТАРЫЙ ПУТЬ: Для обратной совместимости ===
        else:
            # === ЭТАП 1: Централизованная загрузка ресурсов ===
            all_prompts = await self._preload_all_prompts()
            all_contracts = await self._preload_all_contracts()

            # === ЭТАП 2: Создание расширенных конфигураций с ресурсами ===
            component_configs = self._resolve_component_configs()

            for comp_type, configs in component_configs.items():
                for name, base_config in configs.items():
                    # Создаем расширенную конфигурацию с предзагруженными ресурсами
                    enriched_config = self._enrich_config_with_resources(
                        base_config,
                        all_prompts,
                        all_contracts
                    )
                    component_configs[comp_type][name] = enriched_config

            # === ЭТАП 3: Создание компонентов с предзагруженными ресурсами ===
            # Создаем ЕДИНСТВЕННЫЙ экземпляр ActionExecutor для всех компонентов
            from core.application.agent.components.action_executor import ActionExecutor
            executor = ActionExecutor(self)

            # Сначала создаем и регистрируем все компоненты
            for comp_type, configs in component_configs.items():
                for name, enriched_config in configs.items():
                    self.logger.info(f"Создание компонента {comp_type.value}.{name}")
                    try:
                        # ЕДИНЫЙ метод создания любого компонента с ActionExecutor
                        component = await self._create_component(comp_type, name, enriched_config, executor)

                        # Регистрация компонента ДО инициализации
                        self.components.register(comp_type, name, component)

                        self.logger.info(f"Компонент {comp_type.value}.{name} успешно создан и зарегистрирован")

                    except Exception as e:
                        self.logger.error(f"Ошибка создания {comp_type.value}.{name}: {e}", exc_info=True)
                        return False

            # === ЭТАП 4: Инициализация компонентов с учетом зависимостей ===
            # Инициализируем компоненты в правильном порядке
            success = await self._initialize_components_with_dependencies()
            if not success:
                self.logger.error("Ошибка инициализации компонентов с учетом зависимостей")
                return False

            # === ЭТАП 5: Валидация готовности системы ===
            if not await self._verify_readiness():
                return False

        # === ЭТАП 4: Инициализация компонентов с учетом зависимостей ===
        # Инициализируем компоненты в правильном порядке
        success = await self._initialize_components_with_dependencies()
        if not success:
            self.logger.error("Ошибка инициализации компонентов с учетом зависимостей")
            return False

        # === ЭТАП 5: Валидация готовности системы ===
        if not await self._verify_readiness():
            return False

        self._initialized = True
        self.logger.info(f"ApplicationContext {self.id} успешно инициализирован")

        return True

    async def _preload_resources_via_repository(self):
        """
        Предзагрузка ресурсов через новый репозиторий.
        Компоненты будут получать готовые объекты при инициализации.
        """
        # Промпты — загружаем в кэш контекста для быстрого доступа компонентами
        self._prompt_cache = {}  # Dict[(capability, version), Prompt]

        for cap, ver in self.config.prompt_versions.items():
            try:
                prompt_obj = self.data_repository.get_prompt(cap, ver)
                self._prompt_cache[(cap, ver)] = prompt_obj
                self.logger.debug(f"Загружен промпт: {cap}@{ver} (тип: {prompt_obj.component_type.value})")
            except Exception as e:
                self.logger.warning(f"Ошибка загрузки промпта {cap}@{ver}: {e}")
                # Не прерываем инициализацию — компонент сам обработает ошибку

        # Также загружаем промпты из компонентных конфигураций
        for comp_type_attr in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
            if hasattr(self.config, comp_type_attr):
                comp_configs = getattr(self.config, comp_type_attr)
                for comp_name, comp_config in comp_configs.items():
                    if hasattr(comp_config, 'prompt_versions'):
                        for cap, ver in comp_config.prompt_versions.items():
                            if (cap, ver) not in self._prompt_cache:  # Не дублируем
                                try:
                                    prompt_obj = self.data_repository.get_prompt(cap, ver)
                                    self._prompt_cache[(cap, ver)] = prompt_obj
                                    self.logger.debug(f"Загружен промпт из компонента {comp_name}: {cap}@{ver} (тип: {prompt_obj.component_type.value})")
                                except Exception as e:
                                    self.logger.warning(f"Ошибка загрузки промпта {cap}@{ver} из компонента {comp_name}: {e}")

        # Контракты — загружаем схемы для валидации
        self._input_contract_schema_cache = {}  # Dict[(capability, version), Type[BaseModel]]
        self._output_contract_schema_cache = {}

        for cap_dir, ver in self.config.input_contract_versions.items():
            cap = cap_dir.rsplit('.', 1)[0]
            try:
                schema_cls = self.data_repository.get_contract_schema(cap, ver, "input")
                self._input_contract_schema_cache[(cap, ver)] = schema_cls
                self.logger.debug(f"Загружена входная схема: {cap}@{ver}")
            except Exception as e:
                self.logger.warning(f"Ошибка загрузки входной схемы {cap}@{ver}: {e}")

        for cap_dir, ver in self.config.output_contract_versions.items():
            cap = cap_dir.rsplit('.', 1)[0]
            try:
                schema_cls = self.data_repository.get_contract_schema(cap, ver, "output")
                self._output_contract_schema_cache[(cap, ver)] = schema_cls
                self.logger.debug(f"Загружена выходная схема: {cap}@{ver}")
            except Exception as e:
                self.logger.warning(f"Ошибка загрузки выходной схемы {cap}@{ver}: {e}")

        # Также загружаем контракты из компонентных конфигураций
        for comp_type_attr in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
            if hasattr(self.config, comp_type_attr):
                comp_configs = getattr(self.config, comp_type_attr)
                for comp_name, comp_config in comp_configs.items():
                    if hasattr(comp_config, 'input_contract_versions'):
                        for cap_dir, ver in comp_config.input_contract_versions.items():
                            cap = cap_dir.rsplit('.', 1)[0]
                            if (cap, ver) not in self._input_contract_schema_cache:  # Не дублируем
                                try:
                                    schema_cls = self.data_repository.get_contract_schema(cap, ver, "input")
                                    self._input_contract_schema_cache[(cap, ver)] = schema_cls
                                    self.logger.debug(f"Загружен входной контракт из компонента {comp_name}: {cap}@{ver}")
                                except Exception as e:
                                    self.logger.warning(f"Ошибка загрузки входного контракта {cap}@{ver} из компонента {comp_name}: {e}")
                    
                    if hasattr(comp_config, 'output_contract_versions'):
                        for cap_dir, ver in comp_config.output_contract_versions.items():
                            cap = cap_dir.rsplit('.', 1)[0]
                            if (cap, ver) not in self._output_contract_schema_cache:  # Не дублируем
                                try:
                                    schema_cls = self.data_repository.get_contract_schema(cap, ver, "output")
                                    self._output_contract_schema_cache[(cap, ver)] = schema_cls
                                    self.logger.debug(f"Загружен выходной контракт из компонента {comp_name}: {cap}@{ver}")
                                except Exception as e:
                                    self.logger.warning(f"Ошибка загрузки выходного контракта {cap}@{ver} из компонента {comp_name}: {e}")

    # === Совместимые методы для компонентов ===
    def get_prompt(self, capability: str, version: Optional[str] = None) -> str:
        """
        Совместимый интерфейс: возвращает текст промпта (как раньше).
        Внутри использует типизированный объект.
        """
        if self.use_data_repository and self.data_repository:
            # Если указана версия, используем её, иначе ищем в конфиге
            if version is None:
                version = self.config.prompt_versions.get(capability)
                if version is None:
                    # Попробуем получить версию из компонентных конфигураций
                    for comp_type in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
                        if hasattr(self.config, comp_type):
                            comp_configs = getattr(self.config, comp_type)
                            for _, comp_config in comp_configs.items():
                                if hasattr(comp_config, 'prompt_versions') and capability in comp_config.prompt_versions:
                                    version = comp_config.prompt_versions[capability]
                                    break
                    if version is None:
                        return ""  # Возвращаем пустую строку, если версия не найдена
            
            if version:  # Только если версия найдена
                try:
                    prompt_obj = self.data_repository.get_prompt(capability, version)
                    return prompt_obj.content
                except Exception:
                    # Если не удалось получить из репозитория, возвращаем пустую строку
                    return ""
        
        # Старый путь через хранилище
        # Возвращаем пустую строку, если не можем найти промпт
        return self._get_cached_prompt(capability, version)

    def get_input_contract_schema(self, capability: str, version: Optional[str] = None) -> Type[BaseModel]:
        """Возвращает скомпилированную схему для валидации входных данных"""
        if self.use_data_repository and self.data_repository:
            # Если указана версия, используем её, иначе ищем в конфиге
            if version is None:
                version = self.config.input_contract_versions.get(capability + ".input")
                if version is None:
                    # Попробуем получить версию из компонентных конфигураций
                    for comp_type in ['service_configs', 'skill_configs', 'tool_configs', 'behavior_configs']:
                        if hasattr(self.config, comp_type):
                            comp_configs = getattr(self.config, comp_type)
                            for _, comp_config in comp_configs.items():
                                if hasattr(comp_config, 'input_contract_versions') and capability + ".input" in comp_config.input_contract_versions:
                                    version = comp_config.input_contract_versions[capability + ".input"]
                                    break
                                # Также проверим без ".input" суффикса
                                elif hasattr(comp_config, 'input_contract_versions') and capability in comp_config.input_contract_versions:
                                    version = comp_config.input_contract_versions[capability]
                                    break
                    if version is None:
                        from pydantic import BaseModel
                        return BaseModel  # Возвращаем базовый класс, если версия не найдена
            
            if version:  # Только если версия найдена
                try:
                    return self.data_repository.get_contract_schema(capability, version, "input")
                except Exception:
                    from pydantic import BaseModel
                    return BaseModel  # Возвращаем базовый класс при ошибке
        
        # Старый путь: парсим схему из словаря
        # Возвращаем базовый класс, если схема не найдена
        from pydantic import BaseModel
        return BaseModel

    def _get_cached_prompt(self, capability: str, version: Optional[str] = None) -> str:
        """Вспомогательный метод для получения промпта из кэша (старый путь)"""
        if version is None:
            version = self.config.prompt_versions.get(capability)
            if version is None:
                return ""
        
        key = (capability, version)
        if key in self._prompt_cache:
            if hasattr(self._prompt_cache[key], 'content'):
                return self._prompt_cache[key].content
            else:
                return str(self._prompt_cache[key])
        return ""

    async def _preload_all_prompts(self) -> Dict[tuple, str]:
        """Загружает ВСЕ промпты из хранилища ОДИН РАЗ"""
        storage = self.infrastructure_context.get_prompt_storage()
        prompts = {}
        
        # Собираем все уникальные (capability, version) из всех конфигов
        unique_prompts = set()
        for comp_type, configs in self._resolve_component_configs().items():
            for config in configs.values():
                for cap, ver in getattr(config, 'prompt_versions', {}).items():
                    unique_prompts.add((cap, ver))
        
        # Загружаем ОДИН РАЗ через инфраструктурное хранилище
        for capability, version in unique_prompts:
            try:
                prompt_obj = await storage.load(capability, version)
                prompts[(capability, version)] = prompt_obj.content
            except Exception as e:
                self.logger.warning(f"Промпт {capability}@{version} не найден или ошибка загрузки: {e}. Пропускаем.")
                # Добавляем пустую строку для отсутствующего промпта, чтобы не было KeyError позже
                prompts[(capability, version)] = ""
        
        self.logger.info(f"Предзагружено {len(prompts)} промптов")
        return prompts

    async def _preload_all_contracts(self) -> Dict[tuple, Dict]:
        """Загружает ВСЕ контракты из хранилища ОДИН РАЗ"""
        storage = self.infrastructure_context.get_contract_storage()
        contracts = {}
        
        # Собираем все уникальные (capability, version, direction) из всех конфигов
        unique_contracts = set()
        for comp_type, configs in self._resolve_component_configs().items():
            for config in configs.values():
                # Входные контракты
                for cap, ver in getattr(config, 'input_contract_versions', {}).items():
                    unique_contracts.add((cap, ver, "input"))

                # Выходные контракты
                for cap, ver in getattr(config, 'output_contract_versions', {}).items():
                    unique_contracts.add((cap, ver, "output"))

        self.logger.info(f"Найдено {len(unique_contracts)} уникальных контрактов для предзагрузки")
        
        # Загружаем ОДИН РАЗ через инфраструктурное хранилище
        loaded_count = 0
        for capability, version, direction in unique_contracts:
            try:
                contract_obj = await storage.load(capability, version, direction)
                contracts[(capability, version, direction)] = contract_obj.schema_data
                loaded_count += 1
                self.logger.debug(f"Загружен контракт {capability}@{version} ({direction}) (поля: {len(contract_obj.schema_data)})")
            except Exception as e:
                self.logger.warning(f"Не удалось загрузить контракт {capability}@{version} ({direction}): {e}")
                # Добавляем пустой словарь для отсутствующего контракта, чтобы не было KeyError позже
                contracts[(capability, version, direction)] = {}

        self.logger.info(f"Предзагружено {loaded_count} из {len(unique_contracts)} контрактов успешно, {len(unique_contracts) - loaded_count} пропущено")
        return contracts

    def _enrich_config_with_resources(
        self,
        base_config: 'ComponentConfig',
        all_prompts: Dict[tuple, str],
        all_contracts: Dict[tuple, Dict]
    ) -> 'ComponentConfig':
        """Добавляет предзагруженные ресурсы в конфигурацию"""
        from copy import deepcopy
        enriched = deepcopy(base_config)
        
        # Заполняем промпты
        enriched.resolved_prompts = {}
        for cap, ver in base_config.prompt_versions.items():
            key = (cap, ver)
            if key in all_prompts:
                enriched.resolved_prompts[cap] = all_prompts[key]
            else:
                # Если промпт не найден, всё равно добавляем его с пустой строкой
                enriched.resolved_prompts[cap] = ""
                self.logger.warning(f"Промпт {key} не найден в предзагруженных ресурсах")
        
        # Заполняем контракты
        enriched.resolved_input_contracts = {}
        for cap, ver in base_config.input_contract_versions.items():
            key = (cap, ver, "input")
            if key in all_contracts:
                enriched.resolved_input_contracts[cap] = all_contracts[key]
            else:
                # Если контракт не найден, всё равно добавляем его с пустым словарем
                enriched.resolved_input_contracts[cap] = {}
                self.logger.warning(f"Входной контракт {key} не найден в предзагруженных ресурсах")
        
        enriched.resolved_output_contracts = {}
        for cap, ver in base_config.output_contract_versions.items():
            key = (cap, ver, "output")
            if key in all_contracts:
                enriched.resolved_output_contracts[cap] = all_contracts[key]
            else:
                # Если контракт не найден, всё равно добавляем его с пустым словарем
                enriched.resolved_output_contracts[cap] = {}
                self.logger.warning(f"Выходной контракт {key} не найден в предзагруженных ресурсах")
        
        return enriched

    async def _initialize_components_with_dependencies(self) -> bool:
        """
        Инициализация компонентов с учетом зависимостей.
        Использует топологическую сортировку для правильного порядка инициализации.
        """
        from core.application.context.application_context import ComponentType
        from collections import defaultdict, deque

        # Получаем все компоненты
        all_components = self.components.all_components()
        
        # Создаем маппинг имени компонента к объекту
        component_map = {comp.name: comp for comp in all_components}

        # Создаем граф зависимостей
        dependency_graph = defaultdict(list)  # component -> [dependencies]
        dependents_graph = defaultdict(list)  # dependency -> [components that depend on it]

        # Собираем зависимости для каждого компонента
        for component in all_components:
            # Проверяем, есть ли у компонента атрибут DEPENDENCIES (как у BaseService)
            deps = []
            if hasattr(component, 'DEPENDENCIES'):
                deps = getattr(component, 'DEPENDENCIES', [])
            elif hasattr(component, 'dependencies'):
                deps = getattr(component, 'dependencies', [])
            else:
                deps = []
            
            dependency_graph[component.name] = deps[:]
            
            # Заполняем обратный граф зависимостей
            for dep in deps:
                dependents_graph[dep].append(component.name)

        # Топологическая сортировка с использованием алгоритма Кана
        # Подсчитываем количество входящих зависимостей (in-degree) для каждого компонента
        in_degree = {comp.name: 0 for comp in all_components}
        
        for component_name in dependency_graph:
            for dep_name in dependency_graph[component_name]:
                if dep_name in in_degree:  # Убедимся, что зависимость существует в системе
                    in_degree[component_name] += 1

        # Инициализируем очередь компонентов без зависимостей (in-degree = 0)
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        initialization_order = []
        
        # Процесс топологической сортировки
        while queue:
            current_component_name = queue.popleft()
            initialization_order.append(current_component_name)
            
            # Уменьшаем in-degree для всех компонентов, зависящих от текущего
            for dependent_name in dependents_graph[current_component_name]:
                if dependent_name in in_degree:
                    in_degree[dependent_name] -= 1
                    # Если in-degree стал 0, добавляем в очередь
                    if in_degree[dependent_name] == 0:
                        queue.append(dependent_name)

        # Проверяем, были ли инициализированы все компоненты (отсутствие циклических зависимостей)
        if len(initialization_order) != len(all_components):
            # Обнаружена циклическая зависимость
            remaining_components = set(in_degree.keys()) - set(initialization_order)
            self.logger.error(f"Обнаружена циклическая зависимость между компонентами: {remaining_components}")
            
            # Попробуем инициализировать оставшиеся компоненты в любом порядке
            all_initialized_names = set(initialization_order)
            for comp in all_components:
                if comp.name not in all_initialized_names:
                    initialization_order.append(comp.name)

        # Инициализируем компоненты в порядке топологической сортировки
        initialized_components = set()

        self.logger.info(f"Инициализация компонентов в порядке зависимостей: {initialization_order}")
        
        for component_name in initialization_order:
            if component_name not in component_map:
                self.logger.warning(f"Компонент {component_name} не найден в карте компонентов")
                continue
                
            component = component_map[component_name]
            
            try:
                if hasattr(component, 'initialize') and callable(component.initialize):
                    if await component.initialize():
                        initialized_components.add(component.name)
                        self.logger.debug(f"Компонент {component.name} инициализирован")
                    else:
                        self.logger.error(f"Компонент {component.name} не смог инициализироваться")
                        return False
                else:
                    initialized_components.add(component.name)
                    self.logger.debug(f"Компонент {component.name} не требует инициализации")
            except Exception as e:
                self.logger.error(f"Ошибка при инициализации компонента {component.name}: {e}")
                return False

        # Проверяем, все ли компоненты были инициализированы
        all_names = {comp.name for comp in all_components}
        if len(initialized_components) != len(all_names):
            uninitialized = all_names - initialized_components
            self.logger.error(f"Не все компоненты были инициализированы: {uninitialized}")
            return False

        self.logger.info(f"Все компоненты успешно инициализированы: {len(all_components)}")
        return True

    async def _validate_manifests_by_profile(self) -> Dict[str, Any]:
        """Валидация всех манифестов по профилю"""
        report = {
            'total_manifests': 0,
            'critical_errors': 0,
            'warnings': 0,
            'error_details': [],
            'warning_details': []
        }
        
        component_configs = self._resolve_component_configs()
        
        for comp_type, configs in component_configs.items():
            for comp_name, config in configs.items():
                report['total_manifests'] += 1
                
                manifest = self.data_repository.get_manifest(comp_type.value, comp_name)
                
                if not manifest:
                    if self.profile == "prod":
                        report['critical_errors'] += 1
                        report['error_details'].append(
                            f"[PROD] Манифест не найден для {comp_type.value}.{comp_name} (из конфигурации)"
                        )
                    else:
                        report['warnings'] += 1
                        report['warning_details'].append(
                            f"[SANDBOX] Манифест не найден для {comp_type.value}.{comp_name} (из конфигурации)"
                        )
                    continue
                
                manifest_errors = self.data_repository.validate_manifest_by_profile(
                    manifest, self.profile
                )
                
                for error in manifest_errors:
                    if self.profile == "prod":
                        report['critical_errors'] += 1
                        report['error_details'].append(f"[PROD] {comp_type.value}.{comp_name}: {error}")
                    else:
                        report['warnings'] += 1
                        report['warning_details'].append(f"[SANDBOX] {comp_type.value}.{comp_name}: {error}")
        
        return report

    async def _verify_readiness(self) -> bool:
        """Валидация, что ВСЕ компоненты готовы к работе"""
        # Проверка, что все компоненты, которые были объявлены в конфигурации, инициализированы

        # Получаем все компоненты, которые должны быть загружены
        declared_components = self._resolve_component_configs()

        self.logger.info(f"Проверка готовности компонентов: {[(k.value, list(v.keys())) for k, v in declared_components.items()]}")

        for comp_type, names in declared_components.items():
            for name in names:
                self.logger.debug(f"Проверка компонента: {comp_type.value}.{name}")
                component = self.components.get(comp_type, name)
                if component is None:
                    self.logger.error(f"Компонент {comp_type.value}.{name} был объявлен в конфигурации, но не загружен")
                    # Дополнительная диагностика
                    all_registered_components = {}
                    for ct in self.components._components:
                        all_registered_components[ct.value] = list(self.components._components[ct].keys())
                    self.logger.error(f"Все зарегистрированные компоненты: {all_registered_components}")
                    return False
                # Проверяем, что компонент инициализирован
                if hasattr(component, '_initialized'):
                    if not component._initialized:
                        self.logger.error(f"Компонент {comp_type.value}.{name} не инициализирован")
                        return False
                    else:
                        self.logger.debug(f"Компонент {comp_type.value}.{name} инициализирован успешно")
                elif hasattr(component, 'is_ready') and callable(component.is_ready):
                    if not component.is_ready():
                        self.logger.error(f"Компонент {component.name} не готов к работе")
                        return False
                else:
                    self.logger.warning(f"Компонент {component.name} не имеет атрибута _initialized или метода is_ready")

        self.logger.info("Все компоненты успешно проверены")
        return True

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности контекста и всех компонентов.
        
        RETURNS:
        - Dict: Отчет о здоровье системы с деталями по каждому компоненту
        """
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
        
        # Проверяем статус самого контекста
        context_healthy = self._initialized
        health_report['context_healthy'] = context_healthy
        
        if not context_healthy:
            health_report['overall_status'] = 'unhealthy'
            health_report['details']['context_error'] = 'ApplicationContext не инициализирован'
        
        # Проверяем каждый компонент
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
            
            # Проверяем статус инициализации
            if hasattr(component, '_initialized'):
                comp_health['initialized'] = component._initialized
                comp_health['ready'] = component._initialized
            else:
                comp_health['ready'] = True  # Если нет флага инициализации, считаем готовым
            
            # Добавляем информацию о зависимостях если они есть
            if hasattr(component, '_dependencies'):
                comp_health['dependencies_count'] = len(component._dependencies)
                comp_health['dependencies'] = list(component._dependencies.keys())
            
            # Определяем статус компонента
            if not comp_health['ready']:
                comp_health['status'] = 'unhealthy'
                health_report['overall_status'] = 'unhealthy'
                health_report['metrics']['unhealthy_components'] += 1
            else:
                comp_health['status'] = 'healthy'
                health_report['metrics']['healthy_components'] += 1
            
            health_report['components_health'][component.name] = comp_health
        
        # Обновляем общее состояние
        if health_report['metrics']['unhealthy_components'] > 0:
            health_report['overall_status'] = 'degraded' if health_report['metrics']['unhealthy_components'] < health_report['metrics']['total_components'] else 'unhealthy'
        elif health_report['metrics']['healthy_components'] == 0:
            health_report['overall_status'] = 'unhealthy'
        
        # Добавляем время выполнения проверки
        health_report['metrics']['check_duration'] = time.time() - start_time
        
        self.logger.info(f"Health check completed: {health_report['overall_status']}, "
                         f"{health_report['metrics']['healthy_components']}/{health_report['metrics']['total_components']} components healthy")
        
        return health_report

    # === ЕДИНЫЕ точки доступа к компонентам ===
    
    def get_service(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.SERVICE, name)
    
    def get_skill(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.SKILL, name)
    
    def get_tool(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.TOOL, name)
    

    def get_behavior_pattern(self, name: str) -> Optional['BaseComponent']:
        return self.components.get(ComponentType.BEHAVIOR, name)

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
                # Если хранилище контрактов не сущест��ует или недоступно, пропускаем валидацию
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
        
        # Скан��руем директории контрактов для определения доступных capability
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

        # В новой архитектуре мы получаем промпт из изолир��ванного сервиса
        prompt_service = self.get_service("prompt_service")
        if prompt_service is None:
            raise RuntimeError("PromptService не инициализирован")
        return prompt_service.get_prompt(capability_name)

    def get_input_contract(self, capability_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение входного контракт�� из изолированного кэша.

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