"""
Прикладной контекст - версионируемый контекст для сессии/агента.

СОДЕРЖИТ:
- Изолированные кэши: промптов, контрактов
- Навыки с изолированными кэшами
- Сессионные сервисы (при необходимости)
- Конфигурацию: ComponentConfig, флаги (side_effects_enabled, detailed_metrics)
- Ссылку на InfrastructureContext (только для чтения)
"""
import uuid
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from core.config.models import AgentConfig
from core.config.component_config import ComponentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.skills.base_skill import BaseSkill
from core.application.services.prompt_service_new import PromptService
from core.application.services.contract_service_new import ContractService


class ApplicationContext:
    """Версионируемый контекст приложения. Создаётся на сессию/агента."""

    def __init__(
        self,
        infrastructure_context: InfrastructureContext,
        config: AgentConfig  # Версионная конфигурация
    ):
        """
        Инициализация прикладного контекста.

        ПАРАМЕТРЫ:
        - infrastructure: Инфраструктурный контекст (только для чтения!)
        - config: Конфигурация агента с версиями компонентов
        """
        self.id = str(uuid.uuid4())
        self.infrastructure_context = infrastructure_context  # Только для чтения!
        self.config = config
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

        # Навыки с изолированными кэшами
        self._skills: Dict[str, BaseSkill] = {}

        # Флаги конфигурации
        self.side_effects_enabled: bool = getattr(config, 'side_effects_enabled', True)
        self.detailed_metrics: bool = getattr(config, 'detailed_metrics', False)

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
        await self._create_isolated_services()

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

    async def _create_isolated_services(self):
        """Создание изолированных сервисов с изолированными кэшами."""
        # Создаем ComponentConfig с версиями из конфигурации приложения
        input_contract_versions = getattr(self.config, 'input_contract_versions', {}) or getattr(self.config, 'contract_versions', {})
        output_contract_versions = getattr(self.config, 'output_contract_versions', {}) or getattr(self.config, 'contract_versions', {})

        component_config = ComponentConfig(
            variant_id=f"app_context_{self.id[:8]}",
            prompt_versions=getattr(self.config, 'prompt_versions', {}),
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

    async def _preload_prompts(self):
        """Предзагрузка промптов в изолированный кэш."""
        if not hasattr(self.config, 'prompt_versions'):
            self.logger.info("Нет конфигурации промптов для предзагрузки")
            return

        # В новой архитектуре промпты уже предзагружены в изолированный кэш сервиса
        # Мы можем скопировать их в кэш прикладного контекста для обратной совместимости
        for capability_name in self.config.prompt_versions.keys():
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
        # Используем component_config из сервисов, так как self.config - это AgentConfig
        # а не ComponentConfig, у которого есть input_contract_versions и output_contract_versions
        if not hasattr(self._contract_service, 'component_config'):
            self.logger.info("Сервис контрактов не инициализирован для предзагрузки")
            return

        input_contract_versions = getattr(self._contract_service.component_config, 'input_contract_versions', {})
        output_contract_versions = getattr(self._contract_service.component_config, 'output_contract_versions', {})

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
        # В текущей архитектуре инструменты могут быть зарегистрированы глобально, но использовать изолированные кэши
        # Для простоты в этом этапе просто регистрируем пустой список инструментов
        # В реальной реализации здесь будет логика обнаружения и создания инструментов с изолированными кэшами
        self.logger.info("Создание инструментов с изолированными кэшами пропущено (реализация в следующем этапе)")

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

        # Создаём новый контекст с ТЕМ ЖЕ инфраструктурным контекстом
        new_ctx = ApplicationContext(
            infrastructure_context=self.infrastructure_context,  # Общий для всех!
            config=new_config
        )
        await new_ctx.initialize()

        return new_ctx