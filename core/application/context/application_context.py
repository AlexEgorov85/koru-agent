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

from core.application.components.tool import BaseTool
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.skills.base_skill import BaseSkill
from core.application.services.prompt_service_new import PromptService
from core.application.services.contract_service_new import ContractService


class ApplicationContext:
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

        # Изолированные кэши
        self._prompt_cache: Dict[str, str] = {}  # capability_name -> prompt_text
        self._input_contract_cache: Dict[str, Dict[str, Any]] = {}  # capability_name -> schema
        self._output_contract_cache: Dict[str, Dict[str, Any]] = {}  # capability_name -> schema

        # Изолированные сервисы
        self._prompt_service: Optional[PromptService] = None
        self._contract_service: Optional[ContractService] = None
        self._table_description_service: Optional[Any] = None  # Будет установлено позже
        self._sql_generation_service: Optional[Any] = None  # Будет установлено позже
        self._sql_query_service: Optional[Any] = None  # Будет установлено позже
        self._sql_validator_service: Optional[Any] = None  # Будет установлено позже

        # Инструменты с изолированными кэшами
        self._tools: Dict[str, BaseTool] = {}
        
        # Навыки с изолированными кэшами
        self._skills: Dict[str, BaseSkill] = {}

        # Флаги конфигурации из AppConfig
        self.side_effects_enabled = config.side_effects_enabled
        self.detailed_metrics = config.detailed_metrics

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.id}")

    async def initialize(self) -> bool:
        """
        Инициализация прикладного контекста:
        1. Создание изолированных сервисов
        2. Загрузка промптов/контрактов в изолированные кэши
        3. Создание навыков с изолированными кэшами
        """
        if self._initialized:
            self.logger.warning("ApplicationContext уже инициализирован")
            return True

        self.logger.info(f"Начало инициализации ApplicationContext {self.id}")

        # 1. Создание изолированных сервисов
        success = await self._create_isolated_services()
        if not success:
            self.logger.error(f"Ошибка создания изолированных сервисов для ApplicationContext {self.id}")
            return False

        # 2. Загрузка промптов в изолированный кэш
        await self._preload_prompts()

        # 3. Загрузка контрактов в изолированный кэш
        await self._preload_contracts()

        # 4. Создание навыков с изолированными кэшами
        await self._create_skills_with_isolated_caches()

        # 5. Создание инструментов с изолированными кэшами
        await self._create_tools_with_isolated_caches()

        self._initialized = True
        self.logger.info(f"ApplicationContext {self.id} успешно инициализирован")

        return True

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

    async def _create_isolated_services(self):
        """Создание изолированных сервисов с изолированными кэшами."""
        # Используем версии из AppConfig с безопасным доступом
        # Для обратной совместимости с сервисами, которые ожидают ComponentConfig
        # извлекаем версии из единой конфигурации (AppConfig)
        
        # Используем прямой доступ к версиям из AppConfig
        input_contract_versions = self.config.input_contract_versions
        output_contract_versions = self.config.output_contract_versions
        
        # Применяем оверрайды версий промптов, если они есть (только для песочницы)
        prompt_versions = getattr(self.config, 'prompt_versions', {}).copy()
        if self.profile == "sandbox":
            prompt_versions.update(self._prompt_overrides)

        # Валидируем версии в зависимости от профиля перед созданием компонентов
        if not await self._validate_versions_by_profile(prompt_versions, input_contract_versions, output_contract_versions):
            self.logger.error(f"Валидация версий не пройдена для профиля {self.profile}")
            return False

        # Создаем ComponentConfig из единой конфигурации (AppConfig) для обратной совместимости
        from core.config.component_config import ComponentConfig
        component_config = ComponentConfig(
            variant_id=f"app_context_{self.id[:8]}",
            prompt_versions=prompt_versions,
            input_contract_versions=input_contract_versions,
            output_contract_versions=output_contract_versions,
            side_effects_enabled=getattr(self.config, 'side_effects_enabled', True),
            detailed_metrics=getattr(self.config, 'detailed_metrics', False)
        )

        # Создание изолированного PromptService (новая архитектура)
        self._prompt_service = PromptService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        success = await self._prompt_service.initialize()
        if not success:
            self.logger.error("Ошибка инициализации PromptService")
            raise RuntimeError("Не удалось инициализировать PromptService")

        # Создание изолированного ContractService (новая архитектура)
        self._contract_service = ContractService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        success = await self._contract_service.initialize()
        if not success:
            self.logger.error("Ошибка инициализации ContractService")
            raise RuntimeError("Не удалось инициализировать ContractService")

        # Создание изолированного TableDescriptionService
        from core.application.services.table_description_service import TableDescriptionService
        self._table_description_service = TableDescriptionService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        await self._table_description_service.initialize()

        # Создание изолированных сервисов-зависимостей
        from core.application.services.sql_generation.service import SQLGenerationService
        from core.application.services.sql_validator.service import SQLValidatorService

        self._sql_generation_service = SQLGenerationService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        success = await self._sql_generation_service.initialize()
        if not success:
            self.logger.error("Ошибка инициализации SQLGenerationService")
            raise RuntimeError("Не удалось инициализировать SQLGenerationService")

        self._sql_validator_service = SQLValidatorService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        success = await self._sql_validator_service.initialize()
        if not success:
            self.logger.error("Ошибка инициализации SQLValidatorService")
            raise RuntimeError("Не удалось инициализировать SQLValidatorService")

        # Создание изолированного SQLQueryService (после зависимостей)
        from core.application.services.sql_query.service import SQLQueryService
        self._sql_query_service = SQLQueryService(
            application_context=self,  # ApplicationContext как прикладной контекст
            component_config=component_config
        )
        success = await self._sql_query_service.initialize()
        if not success:
            self.logger.error("Ошибка инициализации SQLQueryService")
            raise RuntimeError("Не удалось инициализировать SQLQueryService")

        self.logger.info("Изолированные сервисы созданы и инициализированы")

        return True

    async def _preload_prompts(self):
        """Предзагрузка промптов в изолированный кэш."""
        # Используем прямой доступ к версиям из AppConfig
        prompt_versions = self.config.prompt_versions
        
        if not prompt_versions:
            self.logger.info("Нет конфигурации промптов для предзагрузки")
            return

        # В новой архитектуре промпты уже предзагружены в изолированный кэш сервиса
        # Мы можем скопировать их в кэш прикладного контекста для обратной совместимости
        for capability_name in prompt_versions.keys():
            try:
                # Получаем промпт из изолированного сервиса
                prompt_text = self._prompt_service.get_prompt(capability_name)

                # Сохраняем в изолированный кэш прикладного контекста
                self._prompt_cache[capability_name] = prompt_text
                self.logger.debug(f"Предзагружен промпт {capability_name} в изолированный кэш")
            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки промпта {capability_name}: {e}")

    async def _preload_contracts(self):
        """Предзагрузка контрактов в изолированный кэш."""
        # Используем прямой доступ к версиям из AppConfig
        input_contract_versions = self.config.input_contract_versions
        output_contract_versions = self.config.output_contract_versions
        
        if not input_contract_versions and not output_contract_versions:
            self.logger.info("Нет конфигурации контрактов для предзагрузки")
            return

        # В новой архитектуре контракты уже предзагружены в изолированный кэш сервиса
        # Мы можем скопировать их в кэш прикладного контекста для обратной совместимости
        for capability_name in input_contract_versions.keys():
            try:
                # Получаем входной контракт из изолированного сервиса
                input_schema = self._contract_service.get_contract(capability_name, "input")

                # Сохраняем в изолированный кэш прикладного контекста
                self._input_contract_cache[capability_name] = input_schema
                self.logger.debug(f"Предзагружен входной контракт {capability_name} в изолированный кэш")
            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки входного контракта {capability_name}: {e}")

        for capability_name in output_contract_versions.keys():
            try:
                # Получаем выходной контракт из изолированного сервиса
                output_schema = self._contract_service.get_contract(capability_name, "output")

                # Сохраняем в изолированный кэш прикладного контекста
                self._output_contract_cache[capability_name] = output_schema
                self.logger.debug(f"Предзагружен выходной контракт {capability_name} в изолированный кэш")
            except Exception as e:
                self.logger.error(f"Ошибка предзагрузки выходного контракта {capability_name}: {e}")

    async def _create_skills_with_isolated_caches(self):
        """Создание навыков с изолированными кэшами."""
        # В текущей архитектуре навыки должны быть обнаружены и созданы с изолированными кэшами
        # Для простоты в этом этапе просто инициализируем пустой словарь навыков
        # В реальной реализации здесь будет логика обнаружения и создания навыков с изолированными кэшами
        self._skills = {}
        self.logger.info("Создание навыков с изолированными кэшами пропущено (реализация в следующем этапе)")

    async def _create_tools_with_isolated_caches(self):
        """Создание инструментов с изолированными кэшами."""
        # В новой архитектуре инструменты создаются с изолированными кэшами в каждом прикладном контексте
        # Получаем конфигурацию инструментов из AppConfig
        tool_configs = getattr(self.config, 'tool_configs', {})
        
        for tool_name, tool_config in tool_configs.items():
            try:
                # Создаем инструмент с изолированным контекстом приложения
                # В реальной системе здесь будет логика фабрики инструментов
                tool_class = self._get_tool_class_by_name(tool_name)
                if tool_class:
                    tool = tool_class(
                        name=tool_name,
                        application_context=self,  # ApplicationContext как прикладной контекст
                        component_config=tool_config
                    )
                    
                    # Инициализируем инструмент
                    if hasattr(tool, 'initialize') and callable(tool.initialize):
                        success = await tool.initialize()
                        if success:
                            self._tools[tool_name] = tool
                            self.logger.info(f"Инструмент '{tool_name}' создан с изолированным контекстом")
                        else:
                            self.logger.error(f"Не удалось инициализировать инструмент '{tool_name}'")
                    else:
                        self._tools[tool_name] = tool
                        self.logger.info(f"Инструмент '{tool_name}' создан (без инициализации)")
                else:
                    self.logger.warning(f"Класс инструмента '{tool_name}' не найден")
            except Exception as e:
                self.logger.error(f"Ошибка создания инструмента '{tool_name}': {e}")
        
        self.logger.info(f"Создано инструментов с изолированными кэшами: {len(self._tools)}")

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
        return self._prompt_service.get_prompt(capability_name)

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
        return self._contract_service.get_contract(capability_name, "input")

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
        return self._contract_service.get_contract(capability_name, "output")

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """Получение навыка по имени."""
        return self._skills.get(skill_name)

    def get_provider(self, name: str):
        """Получение провайдера через инфраструктурный контекст."""
        return self.infrastructure_context.get_provider(name)

    def get_tool(self, name: str):
        """Получение инструмента через инфраструктурный контекст."""
        return self.infrastructure_context.get_tool(name)

    def get_service(self, name: str):
        """Получение сервиса из изолированного контекста приложения."""
        if name == "prompt_service":
            return self._prompt_service
        elif name == "contract_service":
            return self._contract_service
        elif name == "table_description_service":
            return self._table_description_service
        elif name == "sql_generation_service":
            return self._sql_generation_service
        elif name == "sql_query_service":
            return self._sql_query_service
        elif name == "sql_validator_service":
            return self._sql_validator_service
        else:
            # Для других сервисов, которые могут быть общими, обращаемся в инфраструктурный контекст
            return self.infrastructure_context.get_service(name)

    def get_prompt_service(self):
        """Получение изолированного сервиса промптов."""
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self._prompt_service

    def get_contract_service(self):
        """Получение изолированного сервиса контрактов."""
        if not self._initialized:
            raise RuntimeError(
                f"ApplicationContext не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self._contract_service

    def get_resource(self, name: str):
        """Получение ресурса - возвращает изолированные сервисы или обращается к инфраструктурному контексту."""
        # Возвращаем изолированные сервисы приложения
        if name == "prompt_service":
            return self._prompt_service
        elif name == "contract_service":
            return self._contract_service
        elif name == "table_description_service":
            return self._table_description_service
        elif name == "sql_generation_service":
            return self._sql_generation_service
        elif name == "sql_query_service":
            return self._sql_query_service
        elif name == "sql_validator_service":
            return self._sql_validator_service
        else:
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