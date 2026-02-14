"""
Инфраструктурный контекст - центральный класс для управления тяжелыми ресурсами.

СОДЕРЖИТ:
- Провайдеры (LLM, DB) - с общими пулами соединений
- Хранилища (без кэширования) - только загрузка из ФС/БД
- Шина событий - глобальная для всех агентов
"""
import uuid
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from core.config.models import SystemConfig
from core.infrastructure.providers.llm.factory import LLMProviderFactory
from core.infrastructure.providers.database.factory import DBProviderFactory
from core.infrastructure.storage.prompt_storage import PromptStorage
from core.infrastructure.storage.contract_storage import ContractStorage
from core.infrastructure.interfaces.storage_interfaces import IPromptStorage, IContractStorage
from core.infrastructure.event_bus.event_bus import EventBus
from core.infrastructure.context.resource_registry import ResourceRegistry
from core.infrastructure.context.lifecycle_manager import LifecycleManager
from core.models.resource import ResourceType, ResourceHealth


class InfrastructureContext:
    """Главный класс инфраструктурного контекста. Создаётся 1 раз за жизненный цикл приложения."""

    def __init__(self, config: SystemConfig):
        """
        Инициализация инфраструктурного контекста.

        ПАРАМЕТРЫ:
        - config: Системная конфигурация
        """
        self.id = str(uuid.uuid4())
        self.config = config
        self._initialized = False

        # Основные компоненты инфраструктуры
        self.lifecycle_manager: Optional[LifecycleManager] = None
        self.event_bus: Optional[EventBus] = None
        self.resource_registry: Optional[ResourceRegistry] = None

        # Фабрики провайдеров
        self.llm_provider_factory: Optional[LLMProviderFactory] = None
        self.db_provider_factory: Optional[DBProviderFactory] = None

        # Инфраструктурные хранилища (только загрузка, без кэширования)
        self.prompt_storage: Optional[IPromptStorage] = None
        self.contract_storage: Optional[IContractStorage] = None

        # Удаляем _tools, так как инструменты должны быть в прикладном контексте

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.id}")

    async def initialize(self) -> bool:
        """
        Инициализация инфраструктурных ресурсов.

        ВАЖНО: После инициализации контекст становится неизменяемым.
        """
        if self._initialized:
            self.logger.warning("InfrastructureContext уже инициализирован")
            return True

        self.logger.info("Начало инициализации InfrastructureContext")

        # Инициализация менеджера жизненного цикла
        self.lifecycle_manager = LifecycleManager()

        # Инициализация реестра ресурсов
        self.resource_registry = ResourceRegistry()

        # Инициализация шины событий
        self.event_bus = EventBus()

        # Инициализация фабрик провайдеров
        self.llm_provider_factory = LLMProviderFactory()
        self.db_provider_factory = DBProviderFactory()

        # Инициализация инфраструктурных хранилищ (только для загрузки, без кэширования)
        from pathlib import Path

        # Используем директории из конфигурации
        prompts_dir = Path(self.config.data_dir) / "prompts"
        self.logger.info(f"Используем путь для промтов: {prompts_dir}")

        self.prompt_storage = PromptStorage(prompts_dir)
        self.logger.info(f"PromptStorage инициализирован с директорией: {self.prompt_storage.prompts_dir}")

        # Для ContractStorage используем директорию из конфигурации
        contracts_dir = Path(self.config.data_dir) / "contracts"
        self.logger.info(f"Используем путь для контрактов: {contracts_dir}")

        self.contract_storage = ContractStorage(contracts_dir)
        self.logger.info(f"ContractStorage инициализирован с директорией: {self.contract_storage.contracts_dir}")

        # Регистрация инициализаторов в менеджере жизненного цикла
        self.lifecycle_manager.register_initializer(self._register_providers_from_config)
        self.lifecycle_manager.register_cleanup(self._cleanup_providers)

        # Инициализация всех ресурсов через менеджер жизненного цикла
        success = await self.lifecycle_manager.initialize_all()
        if success:
            self._initialized = True
            self.logger.info("InfrastructureContext успешно инициализирован")

        return success

    async def _register_providers_from_config(self):
        """Регистрация провайдеров из конфигурации."""
        # Регистрация LLM провайдеров
        first_llm_registered = False
        for provider_name, provider_config in self.config.llm_providers.items():
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    if provider_type == "mock":
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        config_obj = MockLLMConfig(**provider_config.parameters)
                    elif provider_type == "llama_cpp":
                        from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
                        config_obj = MockLlamaCppConfig(**provider_config.parameters)
                    else:
                        # For other providers, try to create a generic config
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        config_obj = MockLLMConfig(**provider_config.parameters)

                    provider = self.llm_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj
                    )
                    
                    # Инициализация провайдера
                    if hasattr(provider, 'initialize') and callable(provider.initialize):
                        await provider.initialize()
                    
                    if provider:
                        # Регистрация LLM провайдера в системе
                        from core.infrastructure.context.resource_registry import ResourceInfo
                        info_llm = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.LLM_PROVIDER,
                            instance=provider
                        )
                        # Устанавливаем первый успешно зарегистрированный провайдер как default
                        info_llm.is_default = not first_llm_registered
                        if not first_llm_registered:
                            first_llm_registered = True
                        self.resource_registry.register_resource(info_llm)
                        self.logger.info(f"LLM провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    self.logger.error(f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}")

        # Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    from core.models.db_types import DBConnectionConfig
                    config_obj = DBConnectionConfig(**provider_config.parameters)

                    provider = self.db_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj
                    )
                    
                    # Инициализация провайдера
                    if hasattr(provider, 'initialize') and callable(provider.initialize):
                        await provider.initialize()
                    
                    if provider:
                        # Регистрация DB провайдера в системе
                        from core.infrastructure.context.resource_registry import ResourceInfo
                        info_db = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.DATABASE,
                            instance=provider
                        )
                        info_db.is_default = True
                        self.resource_registry.register_resource(info_db)
                        self.logger.info(f"DB провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    self.logger.error(f"Ошибка регистрации DB провайдера '{provider_name}': {str(e)}")

    async def _cleanup_providers(self):
        """Очистка провайдеров при завершении работы."""
        # Получаем все провайдеры из реестра ресурсов
        llm_providers = self.resource_registry.get_resources_by_type(ResourceType.LLM_PROVIDER)
        db_providers = self.resource_registry.get_resources_by_type(ResourceType.DATABASE)
        
        # Объединяем все провайдеры
        all_providers = llm_providers + db_providers
        
        for resource_info in all_providers:
            provider = resource_info.instance
            provider_name = resource_info.name
            
            try:
                if hasattr(provider, 'shutdown') and callable(provider.shutdown):
                    await provider.shutdown()
                self.logger.info(f"Провайдер '{provider_name}' завершен")
            except Exception as e:
                self.logger.error(f"Ошибка при завершении провайдера '{provider_name}': {str(e)}")

        # Завершение работы хранилищ
        if self.prompt_storage and hasattr(self.prompt_storage, 'shutdown'):
            await self.prompt_storage.shutdown()
        if self.contract_storage and hasattr(self.contract_storage, 'shutdown'):
            await self.contract_storage.shutdown()

    def get_provider(self, name: str):
        """Получение провайдера по имени."""
        resource_info = self.resource_registry.get_resource(name)
        if resource_info:
            return resource_info.instance
        return None



    def get_resource(self, name: str):
        """Получение ресурса по имени."""
        # Попробуем найти в реестре ресурсов
        resource_info = self.resource_registry.get_resource(name)
        if resource_info:
            return resource_info.instance
        # Также проверим специальные хранилища
        if name == "prompt_storage":
            return self.prompt_storage
        elif name == "contract_storage":
            return self.contract_storage
        # Убрали возврат инструментов и capability_registry, так как они должны быть в прикладном контексте
        return None

    # Методы для доступа из прикладного слоя
    def get_prompt_storage(self) -> IPromptStorage:
        if not hasattr(self, 'prompt_storage'):
            raise RuntimeError("PromptStorage не инициализирован")
        return self.prompt_storage

    def get_contract_storage(self) -> IContractStorage:
        if not hasattr(self, 'contract_storage'):
            raise RuntimeError("ContractStorage не инициализирован")
        return self.contract_storage

    def __setattr__(self, name, value):
        """Запрет на изменение после инициализации."""
        if hasattr(self, '_initialized') and self._initialized and name != '_initialized':
            raise AttributeError(f"InfrastructureContext is immutable after initialization")
        super().__setattr__(name, value)

    async def shutdown(self):
        """Завершение работы инфраструктурного контекста."""
        if not self._initialized:
            return

        self.logger.info("Начало завершения работы InfrastructureContext")

        # Завершение работы через менеджер жизненного цикла
        if self.lifecycle_manager:
            await self.lifecycle_manager.cleanup_all()

        self._initialized = False
        self.logger.info("InfrastructureContext завершил работу")