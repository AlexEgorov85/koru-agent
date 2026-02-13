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
from core.infrastructure.storage.capability_registry import CapabilityRegistry
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
        # Общая фабрика для инструментов, навыков и сервисов
        self.provider_factory: Optional['ProviderFactory'] = None

        # Инфраструктурные хранилища (только загрузка, без кэширования)
        self.prompt_storage: Optional[PromptStorage] = None
        self.contract_storage: Optional[ContractStorage] = None
        self.capability_registry: Optional[CapabilityRegistry] = None

        # Общие ресурсы (провайдеры)
        self._providers: Dict[str, Any] = {}
        # Инструменты
        self._tools: Dict[str, Any] = {}
        # Сервисы
        self._services: Dict[str, Any] = {}

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

        # Инициализация общей фабрики
        from core.infrastructure.providers.factory import ProviderFactory
        self.provider_factory = ProviderFactory(self)

        # Инициализация инфраструктурных хранилищ (только для загрузки, без кэширования)
        from pathlib import Path
        
        # Для PromptStorage используем директорию из конфигурации или по умолчанию "prompts"
        prompts_dir = Path(self.config.data_dir) / "prompts" if hasattr(self.config, 'data_dir') and self.config.data_dir else Path("prompts")
        self.prompt_storage = PromptStorage(prompts_dir)

        # Для ContractStorage используем директорию из конфигурации или по умолчанию "contracts"
        contracts_dir = Path(self.config.data_dir) / "contracts" if hasattr(self.config, 'data_dir') and self.config.data_dir else Path("contracts")
        self.contract_storage = ContractStorage(contracts_dir)

        self.capability_registry = CapabilityRegistry()
        await self.capability_registry.initialize()

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
                    if provider_config.type_provider == "mock":
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        config_obj = MockLLMConfig(**provider_config.parameters)
                    elif provider_config.type_provider == "llama_cpp":
                        from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
                        config_obj = MockLlamaCppConfig(**provider_config.parameters)
                    else:
                        # For other providers, try to create a generic config
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        config_obj = MockLLMConfig(**provider_config.parameters)
                        
                    provider = self.llm_provider_factory.create_provider(
                        provider_type=provider_config.type_provider,
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
                        self._providers[provider_name] = provider
                        self.logger.info(f"LLM провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    self.logger.error(f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}")

        # Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    from core.models.db_types import DBConnectionConfig
                    config_obj = DBConnectionConfig(**provider_config.parameters)
                    
                    provider = self.db_provider_factory.create_provider(
                        provider_type=provider_config.type_provider,
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
                        self._providers[provider_name] = provider
                        self.logger.info(f"DB провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    self.logger.error(f"Ошибка регистрации DB провайдера '{provider_name}': {str(e)}")

    async def _cleanup_providers(self):
        """Очистка провайдеров при завершении работы."""
        for provider_name, provider in self._providers.items():
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
        if self.capability_registry and hasattr(self.capability_registry, 'shutdown'):
            await self.capability_registry.shutdown()

    def get_provider(self, name: str):
        """Получение провайдера по имени."""
        return self._providers.get(name)

    def register_tool(self, name: str, tool: Any):
        """Регистрация инструмента."""
        self._tools[name] = tool
        self.logger.info(f"Инструмент '{name}' зарегистрирован")

    def get_tool(self, name: str):
        """Получение инструмента по имени."""
        return self._tools.get(name)

    def register_service(self, name: str, service: Any):
        """Регистрация сервиса."""
        self._services[name] = service
        self.logger.info(f"Сервис '{name}' зарегистрирован")

    def get_service(self, name: str):
        """Получение сервиса по имени."""
        return self._services.get(name)

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
        elif name == "capability_registry":
            return self.capability_registry
        elif name in self._providers:
            return self._providers[name]
        elif name in self._tools:
            return self._tools[name]
        elif name in self._services:
            return self._services[name]
        return None

    # Методы для доступа из прикладного слоя
    def get_prompt_storage(self) -> 'PromptStorage':
        if not hasattr(self, 'prompt_storage'):
            raise RuntimeError("PromptStorage не инициализирован")
        return self.prompt_storage

    def get_contract_storage(self) -> 'ContractStorage':
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