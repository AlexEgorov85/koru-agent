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
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure.context.resource_registry import ResourceRegistry
from core.infrastructure.context.lifecycle_manager import LifecycleManager
from core.models.data.resource import ResourceInfo
from core.models.enums.common_enums import ResourceType

# Импорты для сборщиков метрик и логов
from core.infrastructure.metrics_storage import FileSystemMetricsStorage
from core.infrastructure.log_storage import FileSystemLogStorage
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.log_collector import LogCollector
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage, ILogStorage


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
        self.event_bus_logger = None  # Будет инициализирован после создания event_bus

        # Основные компоненты инфраструктуры
        self.lifecycle_manager: Optional[LifecycleManager] = None
        # Шина событий: UnifiedEventBus или EventBusConcurrent в зависимости от флага
        self.event_bus: Optional[UnifiedEventBus | EventBusConcurrent] = None
        self.resource_registry: Optional[ResourceRegistry] = None

        # Фабрики провайдеров
        self.llm_provider_factory: Optional[LLMProviderFactory] = None
        self.db_provider_factory: Optional[DBProviderFactory] = None

        # Инфраструктурные хранилища (только загрузка, без кэширования)
        self.prompt_storage: Optional[IPromptStorage] = None
        self.contract_storage: Optional[IContractStorage] = None

        # Хранилища метрик и логов
        self.metrics_storage: Optional[IMetricsStorage] = None
        self.log_storage: Optional[ILogStorage] = None

        # Сборщики метрик и логов
        self.metrics_collector: Optional[MetricsCollector] = None
        self.log_collector: Optional[LogCollector] = None

        # Vector Search провайдеры
        self._faiss_providers: Dict[str, Any] = {}
        self._embedding_provider: Optional[Any] = None
        self._chunking_strategy: Optional[Any] = None

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.id}")

    async def _log_event_bus_info(self, bus_type: str) -> None:
        """
        Логирование информации о выбранной шине событий.

        ПАРАМЕТРЫ:
        - bus_type: тип выбранной шины
        """
        self.logger.info("Используется шина событий: %s", bus_type)

    async def initialize(self) -> bool:
        """
        Инициализация инфраструктурных ресурсов.

        ВАЖНО: После инициализации контекст становится неизменяемым.
        """
        if self._initialized:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("InfrastructureContext уже инициализирован")
            return True

        # === ЭТАП 1: Базовая инициализация ===

        # Инициализация шины событий (ПЕРВЫЙ компонент)
        # Используем UnifiedEventBus — единую шину событий
        self.event_bus = UnifiedEventBus()
        await self._log_event_bus_info("UnifiedEventBus")

        # Инициализация event_bus_logger после создания event_bus
        from core.infrastructure.event_bus.unified_logger import EventBusLogger
        self.event_bus_logger = EventBusLogger(
            self.event_bus,
            session_id=self.id,
            agent_id="infrastructure",
            component="InfrastructureContext"
        )

        # Инициализация менеджера жизненного цикла (нужен event_bus)
        self.lifecycle_manager = LifecycleManager(self.event_bus)

        # Инициализация реестра ресурсов
        self.resource_registry = ResourceRegistry()

        self.logger.info("Начало инициализации InfrastructureContext (через logging)")
        await self.event_bus_logger.info("Начало инициализации InfrastructureContext")

        # === ЭТАП 2: Фабрики провайдеров ===
        self.logger.info("ЭТАП 2: Инициализация фабрик провайдеров")

        # Инициализация фабрик провайдеров
        self.llm_provider_factory = LLMProviderFactory()
        self.db_provider_factory = DBProviderFactory()
        self.logger.info(f"Фабрики созданы. llm_providers в конфиге: {len(self.config.llm_providers) if hasattr(self.config, 'llm_providers') else 'N/A'}")

        # === ЭТАП 3: Инфраструктурные хранилища ===
        self.logger.info("ЭТАП 3: Инициализация хранилищ")

        from pathlib import Path

        # Используем директории из конфигурации
        prompts_dir = Path(self.config.data_dir) / "prompts"
        await self.event_bus_logger.info(f"Используем путь для промтов: {prompts_dir}")

        self.prompt_storage = PromptStorage(prompts_dir)
        await self.event_bus_logger.info(f"PromptStorage инициализирован с директорией: {self.prompt_storage.storage_dir}")

        # Для ContractStorage используем директорию из конфигурации
        contracts_dir = Path(self.config.data_dir) / "contracts"
        await self.event_bus_logger.info(f"Используем путь для контрактов: {contracts_dir}")

        self.contract_storage = ContractStorage(contracts_dir)
        await self.event_bus_logger.info(f"ContractStorage инициализирован с директорией: {self.contract_storage.storage_dir}")

        # Инициализация хранилищ метрик и логов
        metrics_dir = Path(self.config.data_dir) / "metrics"
        logs_dir = Path(self.config.data_dir) / "logs"

        self.metrics_storage = FileSystemMetricsStorage(metrics_dir)
        await self.event_bus_logger.info(f"MetricsStorage инициализирован с директорией: {self.metrics_storage.base_dir}")

        self.log_storage = FileSystemLogStorage(logs_dir)
        await self.event_bus_logger.info(f"LogStorage инициализирован с директорией: {self.log_storage.base_dir}")

        # === ЭТАП 4: Сборщики метрик и логов ===
        
        self.metrics_collector = MetricsCollector(self.event_bus, self.metrics_storage)
        await self.metrics_collector.initialize()
        await self.event_bus_logger.info(f"MetricsCollector инициализирован ({self.metrics_collector.subscriptions_count} подписок)")

        self.log_collector = LogCollector(self.event_bus, self.log_storage)
        await self.log_collector.initialize()
        await self.event_bus_logger.info(f"LogCollector инициализирован ({self.log_collector.subscriptions_count} подписок)")

        # === ЭТАП 5: Vector Search ===
        await self.event_bus_logger.info("ЭТАП 5: Инициализация Vector Search")
        # Инициализация Vector Search
        if self.config.vector_search and self.config.vector_search.enabled:
            await self.event_bus_logger.info("Vector Search включен, начинаем инициализацию...")
            await self._init_vector_search()
        else:
            await self.event_bus_logger.info("Vector Search отключен или не настроен, пропускаем")

        # === ЭТАП 6: Регистрация провайдеров через LifecycleManager ===
        await self.event_bus_logger.info("ЭТАП 6: Регистрация провайдеров через LifecycleManager")

        # Регистрация инициализаторов в менеджере жизненного цикла
        try:
            self.lifecycle_manager.register_initializer(self._register_providers_from_config)
            await self.event_bus_logger.info(f"Зарегистрирован инициализатор _register_providers_from_config. Всего инициализаторов: {len(self.lifecycle_manager._initializers)}")
            self.lifecycle_manager.register_cleanup(self._cleanup_providers)

            # Инициализация всех ресурсов через менеджер жизненного цикла
            await self.event_bus_logger.info("Вызов lifecycle_manager.initialize_all()...")
            success = await self.lifecycle_manager.initialize_all()
            await self.event_bus_logger.info(f"lifecycle_manager.initialize_all() завершен с успехом={success}")
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка на ЭТАПЕ 6: {str(e)}", exc_info=True)
            success = False
            
        if success:
            self._initialized = True
            await self.event_bus_logger.info("InfrastructureContext успешно инициализирован")

        return success

    async def _register_providers_from_config(self):
        """Регистрация провайдеров из конфигурации."""
        import sys
        sys.stdout.write(f'[DEBUG] Начало регистрации провайдеров. llm_providers count={len(self.config.llm_providers)}\n')
        sys.stdout.flush()
        await self.event_bus_logger.info(f"Начало регистрации провайдеров. llm_providers count={len(self.config.llm_providers)}")
        
        # Регистрация LLM провайдеров
        first_llm_registered = False
        for provider_name, provider_config in self.config.llm_providers.items():
            await self.event_bus_logger.info(f"Обработка LLM провайдера '{provider_name}': enabled={getattr(provider_config, 'enabled', False)}")
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    await self.event_bus_logger.info(f"Создание провайдера типа '{provider_type}' для '{provider_name}'")
                    sys.stdout.write(f'[DEBUG] provider_type={provider_type}\n')
                    sys.stdout.flush()
                    if provider_type == "mock":
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        sys.stdout.write(f'[DEBUG] Создание MockLLMConfig...\n')
                        sys.stdout.flush()
                        config_obj = MockLLMConfig(**provider_config.parameters)
                        sys.stdout.write(f'[DEBUG] MockLLMConfig создан\n')
                        sys.stdout.flush()
                    elif provider_type == "llama_cpp":
                        from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
                        sys.stdout.write(f'[DEBUG] Создание MockLlamaCppConfig...\n')
                        sys.stdout.flush()
                        config_obj = MockLlamaCppConfig(**provider_config.parameters)
                        sys.stdout.write(f'[DEBUG] MockLlamaCppConfig создан\n')
                        sys.stdout.flush()
                    else:
                        # For other providers, try to create a generic config
                        from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                        config_obj = MockLLMConfig(**provider_config.parameters)

                    sys.stdout.write(f'[DEBUG] Вызов create_provider...\n')
                    sys.stdout.flush()
                    provider = self.llm_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj
                    )
                    sys.stdout.write(f'[DEBUG] Провайдер создан: {provider is not None}, type={type(provider).__name__ if provider else None}\n')
                    sys.stdout.flush()
                    await self.event_bus_logger.info(f"Провайдер создан: {provider is not None}")

                    # Инициализация провайдера
                    if hasattr(provider, 'initialize') and callable(provider.initialize):
                        sys.stdout.write(f'[DEBUG] Вызов provider.initialize()...\n')
                        sys.stdout.flush()
                        try:
                            await provider.initialize()
                            sys.stdout.write(f'[DEBUG] provider.initialize() завершён успешно\n')
                            sys.stdout.flush()
                        except Exception as init_error:
                            sys.stdout.write(f'[DEBUG] Ошибка в provider.initialize(): {init_error}\n')
                            sys.stdout.flush()
                            raise
                        await self.event_bus_logger.info(f"Провайдер инициализирован")

                    if provider:
                        # Регистрация LLM провайдера в системе
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
                        await self.event_bus_logger.info(f"LLM провайдер '{provider_name}' успешно зарегистрирован")
                        sys.stdout.write(f'[DEBUG] LLM провайдер {provider_name} зарегистрирован\n')
                        sys.stdout.flush()
                except Exception as e:
                    await self.event_bus_logger.error(f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}", exc_info=True)
                    sys.stdout.write(f'[DEBUG] Ошибка LLM {provider_name}: {e}\n')
                    sys.stdout.flush()

        # Регистрация DB провайдеров
        sys.stdout.write(f'[DEBUG] Регистрация DB провайдеров. db_providers count={len(self.config.db_providers)}\n')
        sys.stdout.flush()
        for provider_name, provider_config in self.config.db_providers.items():
            sys.stdout.write(f'[DEBUG] Обработка DB провайдера {provider_name}: enabled={getattr(provider_config, "enabled", False)}\n')
            sys.stdout.flush()
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    sys.stdout.write(f'[DEBUG] Создание DB провайдера типа {provider_type}\n')
                    sys.stdout.flush()
                    from core.models.types.db_types import DBConnectionConfig
                    config_obj = DBConnectionConfig(**provider_config.parameters)

                    provider = self.db_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj
                    )
                    sys.stdout.write(f'[DEBUG] DB провайдер создан: {provider is not None}\n')
                    sys.stdout.flush()

                    # Инициализация провайдера
                    if hasattr(provider, 'initialize') and callable(provider.initialize):
                        sys.stdout.write(f'[DEBUG] Вызов DB provider.initialize()...\n')
                        sys.stdout.flush()
                        try:
                            await provider.initialize()
                            sys.stdout.write(f'[DEBUG] DB provider.initialize() завершён\n')
                            sys.stdout.flush()
                        except Exception as init_err:
                            sys.stdout.write(f'[DEBUG] Ошибка в DB initialize(): {init_err}\n')
                            sys.stdout.flush()
                            raise

                    if provider:
                        # Регистрация DB провайдера в системе
                        info_db = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.DATABASE,
                            instance=provider
                        )
                        info_db.is_default = True
                        self.resource_registry.register_resource(info_db)
                        sys.stdout.write(f'[DEBUG] DB провайдер {provider_name} зарегистрирован\n')
                        sys.stdout.flush()
                        await self.event_bus_logger.info(f"DB провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    sys.stdout.write(f'[DEBUG] Ошибка DB {provider_name}: {e}\n')
                    sys.stdout.flush()
                    await self.event_bus_logger.error(f"Ошибка регистрации DB провайдера '{provider_name}': {str(e)}")

    async def _init_vector_search(self):
        """Инициализация векторного поиска."""
        from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
        from pathlib import Path
        
        vs_config = self.config.vector_search
        self.event_bus_logger.info("Инициализация Vector Search...")
        
        # Инициализация FAISS провайдеров для каждого источника
        for source, index_file in vs_config.indexes.items():
            try:
                provider = FAISSProvider(
                    dimension=vs_config.embedding.dimension,
                    config=vs_config.faiss
                )
                await provider.initialize()
                
                # Загрузка индекса если существует
                index_path = Path(vs_config.storage.base_path) / index_file
                if index_path.exists():
                    await provider.load(str(index_path))
                    self.event_bus_logger.info(f"✅ Загружен индекс {source}: {index_path}")
                
                
                self._faiss_providers[source] = provider
            except Exception as e:
                self.event_bus_logger.error(f"Ошибка инициализации FAISS провайдера {source}: {e}")
        
        # Инициализация Embedding провайдера
        try:
            self._embedding_provider = SentenceTransformersProvider(vs_config.embedding)
            await self._embedding_provider.initialize()
            self.event_bus_logger.info(f"✅ Инициализирован Embedding: {vs_config.embedding.model_name}")
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка инициализации Embedding провайдера: {e}")
        
        # Инициализация Chunking стратегии
        try:
            self._chunking_strategy = TextChunkingStrategy(
                chunk_size=vs_config.chunking.chunk_size,
                chunk_overlap=vs_config.chunking.chunk_overlap,
                min_chunk_size=vs_config.chunking.min_chunk_size
            )
            self.event_bus_logger.info(f"✅ Инициализирован Chunking: {vs_config.chunking.chunk_size} символов")
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка инициализации Chunking стратегии: {e}")

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
                await self.event_bus_logger.info(f"Провайдер '{provider_name}' завершен")
            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка при завершении провайдера '{provider_name}': {str(e)}")

        # Завершение работы хранилищ
        if self.prompt_storage and hasattr(self.prompt_storage, 'shutdown'):
            await self.prompt_storage.shutdown()
        if self.contract_storage and hasattr(self.contract_storage, 'shutdown'):
            await self.contract_storage.shutdown()

        # Завершение сборщиков метрик и логов
        if self.metrics_collector:
            await self.metrics_collector.shutdown()
        if self.log_collector:
            await self.log_collector.shutdown()

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

    def get_metrics_storage(self) -> IMetricsStorage:
        if not hasattr(self, 'metrics_storage'):
            raise RuntimeError("MetricsStorage не инициализирован")
        return self.metrics_storage

    def get_log_storage(self) -> ILogStorage:
        if not hasattr(self, 'log_storage'):
            raise RuntimeError("LogStorage не инициализирован")
        return self.log_storage

    def get_metrics_collector(self) -> MetricsCollector:
        if not hasattr(self, 'metrics_collector'):
            raise RuntimeError("MetricsCollector не инициализирован")
        return self.metrics_collector

    def get_log_collector(self) -> LogCollector:
        if not hasattr(self, 'log_collector'):
            raise RuntimeError("LogCollector не инициализирован")
        return self.log_collector

    def __setattr__(self, name, value):
        """Запрет на изменение после инициализации."""
        if hasattr(self, '_initialized') and self._initialized and name != '_initialized':
            raise AttributeError(f"InfrastructureContext is immutable after initialization")
        super().__setattr__(name, value)

    async def call_llm(
        self,
        request: str,
        provider_name: Optional[str] = None,
        fallback: bool = True
    ):
        """
        Вызов LLM через инфраструктурный контекст.
        
        ПАРАМЕТРЫ:
        - request: Запрос к LLM
        - provider_name: Имя провайдера (опционально)
          * Если указано → используется конкретный провайдер
          * Если None → используется default провайдер
        - fallback: Использовать fallback стратегию при ошибке
          * Если True → при ошибке пытается использовать backup
          * Если False → выбрасывает исключение при ошибке
        
        ВОЗВРАЩАЕТ:
        - str: Ответ от LLM
        
        ИСПОЛЬЗОВАНИЕ:
        # Default LLM
        response = await infra.call_llm("Привет!")
        
        # Конкретная LLM
        response = await infra.call_llm("Привет!", provider_name="primary_llm")
        
        # Конкретная LLM без fallback
        response = await infra.call_llm("Привет!", provider_name="primary_llm", fallback=False)
        """
        # 1. Получаем запрошенную LLM
        llm = None
        
        if provider_name:
            # Попытка получить конкретный провайдер по имени
            resource_info = self.resource_registry.get_resource(provider_name)
            if resource_info:
                llm = resource_info.instance
                self.event_bus_logger.debug(f"Используем LLM провайдер: {provider_name}")
            
                if not fallback:
                    raise ValueError(f"LLM провайдер '{provider_name}' не найден")
        
        # 2. Если не найдено, пробуем default
        if llm is None:
            llm = self._get_default_llm()
            if llm:
                self.event_bus_logger.debug("Используем default LLM провайдер")
        
        # 3. Если всё ещё нет, пробуем первый доступный
        if llm is None:
            llm = self._get_first_available_llm()
            if llm:
                self.event_bus_logger.warning("Default LLM не найден, используем первый доступный")
        
        # 4. Если вообще нет LLM → ошибка
        if llm is None:
            raise ValueError("Нет доступных LLM провайдеров")
        
        # 5. Вызов провайдера
        try:
            response = await llm.generate(request)
            return response
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка LLM провайдера: {e}")
            
            if fallback and provider_name:
                # Пытаемся использовать backup
                self.event_bus_logger.warning("Попытка fallback на backup LLM")
                backup_llm = self._get_backup_llm(exclude_name=provider_name)
                
                if backup_llm:
                    try:
                        response = await backup_llm.generate(request)
                        return response
                    except Exception as backup_error:
                        self.event_bus_logger.error(f"Backup LLM также не удался: {backup_error}")
            
            # Если fallback не помог или не запрошен
            raise

    def _get_default_llm(self):
        """Получение default LLM провайдера."""
        for info in self.resource_registry.all():
            if info.resource_type == ResourceType.LLM_PROVIDER and info.is_default:
                return info.instance
        return None

    def _get_first_available_llm(self):
        """Получение первого доступного LLM провайдера."""
        for info in self.resource_registry.all():
            if info.resource_type == ResourceType.LLM_PROVIDER:
                return info.instance
        return None

    def _get_backup_llm(self, exclude_name: str):
        """
        Получение backup LLM провайдера (исключая указанный).

        ПАРАМЕТРЫ:
        - exclude_name: Имя провайдера для исключения

        ВОЗВРАЩАЕТ:
        - LLM провайдер или None
        """
        for info in self.resource_registry.all():
            if (info.resource_type == ResourceType.LLM_PROVIDER and
                info.name != exclude_name):
                return info.instance
        return None

    # Vector Search методы доступа

    def get_faiss_provider(self, source: str) -> Optional[Any]:
        """Получение FAISS провайдера по источнику."""
        return self._faiss_providers.get(source)

    def get_embedding_provider(self) -> Optional[Any]:
        """Получение Embedding провайдера."""
        return self._embedding_provider

    def get_chunking_strategy(self) -> Optional[Any]:
        """Получение Chunking стратегии."""
        return self._chunking_strategy

    async def shutdown(self):
        """Завершение работы инфраструктурного контекста."""
        if not self._initialized:
            return

        await self.event_bus_logger.info("Начало завершения работы InfrastructureContext")

        # Сохранение Vector Search индексов
        if self._faiss_providers and self.config.vector_search:
            self.event_bus_logger.info("Сохранение Vector Search индексов...")
            from pathlib import Path
            for source, provider in self._faiss_providers.items():
                try:
                    index_path = Path(self.config.vector_search.storage.base_path) / f"{source}_index.faiss"
                    index_path.parent.mkdir(parents=True, exist_ok=True)
                    await provider.save(str(index_path))
                    self.event_bus_logger.info(f"💾 Сохранён индекс {source}: {index_path}")
                except Exception as e:
                    self.event_bus_logger.error(f"Ошибка сохранения индекса {source}: {e}")
        
        # Завершение Vector Search провайдеров
        for source, provider in self._faiss_providers.items():
            try:
                await provider.shutdown()
            except Exception as e:
                self.event_bus_logger.error(f"Ошибка завершения FAISS провайдера {source}: {e}")
        
        if self._embedding_provider:
            try:
                await self._embedding_provider.shutdown()
            except Exception as e:
                self.event_bus_logger.error(f"Ошибка завершения Embedding провайдера: {e}")

        # Завершение работы через менеджер жизненного цикла
        if self.lifecycle_manager:
            await self.lifecycle_manager.cleanup_all()

        self._initialized = False
        await self.event_bus_logger.info("InfrastructureContext завершил работу")