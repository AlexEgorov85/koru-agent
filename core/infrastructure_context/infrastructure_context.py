"""
Инфраструктурный контекст - центральный класс для управления тяжелыми ресурсами.

СОДЕРЖИТ:
- Провайдеры (LLM, DB) - с общими пулами соединений
- Хранилища (без кэширования) - только загрузка из ФС/БД
- Шина событий - глобальная для всех агентов

ЖИЗНЕННЫЙ ЦИКЛ:
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
"""
import uuid
from typing import Dict, Optional, Any, TYPE_CHECKING
from datetime import datetime

from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
from core.infrastructure.providers.llm.openrouter_provider import OpenRouterConfig
from core.infrastructure.providers.llm.vllm_provider import VLLMConfig
from core.infrastructure_context.lifecycle_manager import LifecycleManager
from core.infrastructure_context.resource_registry import ResourceRegistry
from core.components.services.metrics_publisher import MetricsPublisher

from core.agent.components.lifecycle import ComponentState
from core.config.app_config import AppConfig
from core.infrastructure.providers.llm.factory import LLMProviderFactory
from core.infrastructure.providers.database.factory import DBProviderFactory
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.models.data.resource import ResourceInfo
from core.models.enums.common_enums import ResourceType
from core.infrastructure.discovery.resource_discovery import ResourceDiscovery

# Импорты для телеметрии
from core.infrastructure.telemetry import TelemetryCollector, init_telemetry
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage
from core.infrastructure.telemetry.handlers.session_handler import SessionLogHandler
from core.infrastructure.telemetry.handlers.terminal_handler import TerminalLogHandler


class InfrastructureContext:
    """Главный класс инфраструктурного контекста. Создаётся 1 раз за жизненный цикл приложения."""

    def __init__(self, config: AppConfig):
        """
        Инициализация инфраструктурного контекста.

        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (AppConfig)
        """
        self.id = str(uuid.uuid4())
        self.config = config
        self.event_bus_logger = None  # Будет инициализирован после создания event_bus

        # Основные компоненты инфраструктуры
        self.lifecycle_manager: Optional[LifecycleManager] = None
        # Шина событий: UnifiedEventBus или EventBusConcurrent в зависимости от флага
        self.event_bus: Optional[UnifiedEventBus] = None
        self.resource_registry: Optional[ResourceRegistry] = None

        # Фабрики провайдеров
        self.llm_provider_factory: Optional[LLMProviderFactory] = None
        self.db_provider_factory: Optional[DBProviderFactory] = None

        # Инфраструктурные хранилища (только загрузка, без кэширования)
        self.resource_discovery: Optional[ResourceDiscovery] = None  # ЕДИНЫЙ экземпляр на всё приложение

        # Хранилище метрик
        self.metrics_storage: Optional[IMetricsStorage] = None

        # Сборщик метрик
        self.metrics_collector: Optional[MetricsCollector] = None

        # Обработчик логов сессии
        self.session_handler: Optional[SessionLogHandler] = None

        # MetricsPublisher для унифицированной публикации метрик
        self.metrics_publisher: Optional[MetricsPublisher] = None

        # Vector Search провайдеры
        self._faiss_providers: Dict[str, Any] = {}
        self._embedding_provider: Optional[Any] = None
        self._chunking_strategy: Optional[Any] = None

    async def _log_event_bus_info(self, bus_type: str) -> None:
        """
        Логирование информации о выбранной шине событий.

        ПАРАМЕТРЫ:
        - bus_type: тип выбранной шины
        """
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("Используется шина событий: %s", bus_type)
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def initialize_sync(self) -> bool:
        """
        СИНХРОННАЯ инициализация инфраструктурных ресурсов.

        ИСПОЛЬЗУЕТ asyncio.run() для выполнения async операций.
        Может вызываться из sync контекста.
        """
        import asyncio
        
        # Создаём новый event loop для инициализации
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Запускаем async инициализацию в новом loop
            result = loop.run_until_complete(self.initialize())
            return result
        finally:
            loop.close()

    async def initialize(self) -> bool:
        """
        Инициализация инфраструктурных ресурсов.

        ВАЖНО: После инициализации контекст становится неизменяемым.
        
        ЖИЗНЕННЫЙ ЦИКЛ:
        - Переводит контекст в состояние INITIALIZING
        - При успехе: READY
        - При ошибке: FAILED
        """
        # Проверка повторной инициализации
        if self.lifecycle_manager and self.lifecycle_manager.is_ready:
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.warning("InfrastructureContext уже инициализирован")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return True
        
        # Проверка на предыдущую ошибку
        if self.lifecycle_manager and self.lifecycle_manager.state == ComponentState.FAILED:
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error("InfrastructureContext в состоянии FAILED")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return False

        # === ЭТАП 1: Базовая инициализация ===
        import sys
        sys.stdout.buffer.write("🚀 Инициализация инфраструктурного контекста...\n".encode('utf-8'))
        sys.stdout.flush()

        # Инициализация шины событий (ПЕРВЫЙ компонент)
        self.event_bus = UnifiedEventBus()
        await self._log_event_bus_info("UnifiedEventBus")

        # Инициализация телеметрии (логи + метрики)
        from pathlib import Path
        
        log_dir = Path(self.config.data_dir) / "logs"
        storage_dir = Path(self.config.data_dir)

        # Единая инициализация всей телеметрии
        self.telemetry = await init_telemetry(
            event_bus=self.event_bus,
            storage_dir=storage_dir,
            log_dir=log_dir,
            enable_terminal=True,
            enable_session_logs=True,
            enable_metrics=True
        )

        # Получение обработчиков для доступа
        self.terminal_handler = self.telemetry.get_terminal_handler()
        self.session_handler = self.telemetry.get_session_handler()
        self.metrics_publisher = self.telemetry.get_metrics_publisher()

        # Информация о сессии
        if self.session_handler:
            session_info = self.session_handler.get_session_info()
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"📝 Логи сессии: {session_info['session_folder']}")

        # Инициализация event_bus_logger ПОСЛЕ подписки обработчиков
        from core.infrastructure.logging import EventBusLogger
        self.event_bus_logger = EventBusLogger(
            self.event_bus,
            session_id=self.id,
            agent_id="infrastructure",
            component="InfrastructureContext"
        )

        if self.event_bus_logger:
            await self.event_bus_logger.info("Обработчики логирования инициализированы")
            await self.event_bus_logger.info("EventBusLogger инициализирован")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Инициализация менеджера жизненного цикла
        from core.infrastructure_context.lifecycle_manager import LifecycleManager
        self.lifecycle_manager = LifecycleManager(self.event_bus)

        # Инициализация реестра ресурсов
        self.resource_registry = ResourceRegistry()

        # === ЭТАП 2: Фабрики провайдеров ===
        self.llm_provider_factory = LLMProviderFactory()
        self.db_provider_factory = DBProviderFactory()

        # === ЭТАП 3: Инфраструктурные хранилища ===
        from pathlib import Path

        # === ЭТАП 3.5: ResourceDiscovery (ЕДИНЫЙ экземпляр) ===
        data_dir = Path(self.config.data_dir)
        # ✅ ИСПОЛЬЗУЕМ профиль из конфигурации, а не жёстко 'prod'
        self.resource_discovery = ResourceDiscovery(
            base_dir=data_dir,
            profile=self.config.profile,  # ← Было: 'prod'
            event_bus=self.event_bus
        )
        # Предзагрузка ресурсов в кэш
        self.resource_discovery.discover_prompts()
        self.resource_discovery.discover_contracts()

        # === ЭТАП 4: Метрики (уже инициализированы в telemetry) ===
        # Доступ через self.telemetry.metrics_publisher

        # === ЭТАП 5: Vector Search ===
        # Инициализация Vector Search
        if self.config.vector_search and self.config.vector_search.enabled:
            await self._init_vector_search()

        # === ЭТАП 6: Регистрация провайдеров через LifecycleManager ===
        # Вызываем регистрацию провайдеров через LifecycleManager
        try:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("=== ЭТАП 6: Регистрация провайдеров через LifecycleManager ===")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self._register_providers_from_config()

            # Инициализация всех зарегистрированных провайдеров через LifecycleManager
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("Вызов lifecycle_manager.initialize_all()...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.lifecycle_manager.initialize_all()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("✅ LifecycleManager инициализирован")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error(f"❌ Ошибка инициализации провайдеров: {str(e)}", exc_info=True)
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return False

        await self.event_bus.publish(
            EventType.USER_RESULT,
            data={"message": "InfrastructureContext инициализирован", "icon": "✅"},
            session_id=str(self.id),
        )
        return True

    async def _register_providers_from_config(self):
        """Регистрация провайдеров из конфигурации."""
        has_llm = hasattr(self.config, 'llm_providers')
        if has_llm and self.config.llm_providers:
            for name, prov in self.config.llm_providers.items():
                if self.event_bus_logger:
                    await self.event_bus_logger.info(f"[LLM] - {name}: enabled={prov.enabled}, type={prov.provider_type}")

            first_llm_registered = False
            for provider_name, provider_config in self.config.llm_providers.items():
                if provider_config.enabled:
                    try:
                        provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                        if provider_type == "mock":
                            config_obj = MockLLMConfig(**provider_config.parameters)
                        elif provider_type == "llama_cpp":
                            params = dict(provider_config.parameters)
                            if hasattr(provider_config, 'timeout_seconds'):
                                params['timeout_seconds'] = provider_config.timeout_seconds
                            config_obj = MockLlamaCppConfig(**params)
                        elif provider_type == "openrouter":
                            params = dict(provider_config.parameters)
                            if 'model_name' not in params:
                                params['model_name'] = provider_config.model_name
                            if 'timeout_seconds' not in params and hasattr(provider_config, 'timeout_seconds'):
                                params['timeout_seconds'] = provider_config.timeout_seconds
                            config_obj = OpenRouterConfig(**params)
                        elif provider_type == "vllm":
                            params = dict(provider_config.parameters)
                            if 'model_name' not in params:
                                params['model_name'] = provider_config.model_name
                            if 'timeout_seconds' not in params and hasattr(provider_config, 'timeout_seconds'):
                                params['timeout_seconds'] = provider_config.timeout_seconds
                            config_obj = VLLMConfig(**params)
                        else:
                            config_obj = MockLLMConfig(**provider_config.parameters)

                        provider = self.llm_provider_factory.create_provider(
                            provider_type=provider_type,
                            config=config_obj
                        )

                        await self.lifecycle_manager.register_resource(
                            name=provider_name,
                            resource=provider,
                            resource_type=ResourceType.LLM,
                            metadata={
                                "is_default": not first_llm_registered,
                                "model_name": provider_config.model_name,
                                "provider_type": provider_type
                            }
                        )

                        info_llm = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.LLM,
                            instance=provider
                        )
                        info_llm.is_default = not first_llm_registered
                        if not first_llm_registered:
                            first_llm_registered = True
                        self.resource_registry.register_resource(info_llm)

                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc()
                        if self.event_bus_logger:
                            await self.event_bus_logger.error(f"[LLM] Error: {str(e)}")
                            await self.event_bus_logger.error(f"Error registering LLM provider '{provider_name}': {tb}")
                        print(f"❌ [LLM] FATAL: Failed to register LLM provider '{provider_name}': {e}")
                        print(f"   Traceback:\n{tb}")
                        raise

        # Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    
                    # Выбираем класс конфигурации в зависимости от типа БД
                    if provider_type == "sqlite":
                        from core.models.types.db_types import SQLiteConnectionConfig
                        config_obj = SQLiteConnectionConfig(**provider_config.parameters)
                    else:
                        from core.models.types.db_types import DBConnectionConfig
                        config_obj = DBConnectionConfig(**provider_config.parameters)

                    provider = self.db_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj
                    )

                    # Регистрация в LifecycleManager
                    db_info = {
                        "provider_type": provider_type
                    }
                    if provider_type == "sqlite":
                        db_info["db_path"] = provider_config.parameters.get("db_path", "")
                    else:
                        db_info["database"] = provider_config.parameters.get("database", "")
                        db_info["host"] = provider_config.parameters.get("host", "localhost")
                        db_info["port"] = provider_config.parameters.get("port", 5432)
                    
                    await self.lifecycle_manager.register_resource(
                        name=provider_name,
                        resource=provider,
                        resource_type=ResourceType.DATABASE,
                        metadata=db_info
                    )

                    # Также регистрируем в resource_registry для обратной совместимости
                    info_db = ResourceInfo(
                        name=provider_name,
                        resource_type=ResourceType.DATABASE,
                        instance=provider
                    )
                    info_db.is_default = True
                    self.resource_registry.register_resource(info_db)
                except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(f"❌ Ошибка регистрации DB провайдера '{provider_name}': {str(e)}", exc_info=True)

    async def _init_vector_search(self):
        """Инициализация векторного поиска с проверкой наличия индексов."""
        from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
        from pathlib import Path

        vs_config = self.config.vector_search
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        await self.event_bus_logger.info("Инициализация Vector Search...")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Инициализация FAISS провайдеров для каждого источника
        indexes_status = {}
        for source, index_file in vs_config.indexes.items():
            try:
                provider = FAISSProvider(
                    dimension=vs_config.embedding.dimension,
                    config=vs_config.faiss
                )
                await provider.initialize()

                index_path = Path(vs_config.storage.base_path) / index_file
                index_exists = index_path.exists()
                
                if index_exists:
                    await provider.load(str(index_path))
                    count = await provider.count()
                    indexes_status[source] = {
                        "status": "loaded",
                        "path": str(index_path),
                        "vectors": count
                    }
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.info(f"✅ Загружен индекс {source}: {index_path} ({count} векторов)")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                else:
                    indexes_status[source] = {
                        "status": "missing",
                        "path": str(index_path),
                        "vectors": 0
                    }
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.warning(f"⚠️ Индекс {source} не найден: {index_path}. Требуется индексация.")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                self._faiss_providers[source] = provider
            except Exception as e:
                indexes_status[source] = {
                    "status": "error",
                    "error": str(e)
                }
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"❌ Ошибка инициализации FAISS провайдера {source}: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                continue

        # Логирование общего статуса
        total_vectors = sum(s.get("vectors", 0) for s in indexes_status.values())
        loaded_count = sum(1 for s in indexes_status.values() if s.get("status") == "loaded")
        missing_count = sum(1 for s in indexes_status.values() if s.get("status") == "missing")
        
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        await self.event_bus_logger.info(
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"Vector Search статус: {loaded_count} загружено, {missing_count} отсутствует, "
            f"всего векторов: {total_vectors}"
        )

        # Инициализация Embedding провайдера
        try:
            self._embedding_provider = SentenceTransformersProvider(vs_config.embedding)
            await self._embedding_provider.initialize()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"✅ Инициализирован Embedding: {vs_config.embedding.model_name}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error(f"Ошибка инициализации Embedding провайдера: {e}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Инициализация Chunking стратегии
        try:
            self._chunking_strategy = TextChunkingStrategy(
                chunk_size=vs_config.chunking.chunk_size,
                chunk_overlap=vs_config.chunking.chunk_overlap,
                min_chunk_size=vs_config.chunking.min_chunk_size
            )
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"✅ Инициализирован Chunking: {vs_config.chunking.chunk_size} символов")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error(f"Ошибка инициализации Chunking стратегии: {e}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Сохранение статуса в контекст для последующей проверки
        self._vector_search_status = indexes_status

    async def _cleanup_providers(self):
        """Очистка провайдеров при завершении работы."""
        # Получаем все провайдеры из реестра ресурсов
        llm_providers = self.resource_registry.get_resources_by_type(ResourceType.LLM)
        db_providers = self.resource_registry.get_resources_by_type(ResourceType.DATABASE)
        
        # Объединяем все провайдеры
        all_providers = llm_providers + db_providers
        
        for resource_info in all_providers:
            provider = resource_info.instance
            provider_name = resource_info.name
            
            try:
                if hasattr(provider, 'shutdown') and callable(provider.shutdown):
                    await provider.shutdown()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.info(f"Провайдер '{provider_name}' завершен")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"Ошибка при завершении провайдера '{provider_name}': {str(e)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Завершение работы хранилищ
        if self.prompt_storage and hasattr(self.prompt_storage, 'shutdown'):
            await self.prompt_storage.shutdown()
        if self.contract_storage and hasattr(self.contract_storage, 'shutdown'):
            await self.contract_storage.shutdown()

        # Завершение сборщика метрик
        if self.metrics_collector:
            await self.metrics_collector.shutdown()

    def get_provider(self, name: str):
        """
        DEPRECATED: Получение провайдера по имени.
        Используйте прямые свойства для доступа к провайдерам.
        """
        import warnings
        warnings.warn(
            "get_provider deprecated. Используйте прямые свойства (db_provider_factory, llm_provider_factory, etc.)",
            DeprecationWarning,
            stacklevel=2
        )
        resource_info = self.resource_registry.get_resource(name)
        if resource_info:
            return resource_info.instance
        return None

    def get_resource(self, name: str):
        """
        DEPRECATED: Получение ресурса по имени.
        Используйте прямые свойства для доступа к ресурсам.
        """
        import warnings
        warnings.warn(
            "get_resource deprecated. Используйте прямые свойства (prompt_storage, contract_storage, etc.)",
            DeprecationWarning,
            stacklevel=2
        )
        # Попробуем найти в реестре ресурсов
        resource_info = self.resource_registry.get_resource(name)
        if resource_info:
            return resource_info.instance
        return None

    # Методы для доступа из прикладного слоя
    # DEPRECATED: Используйте свойства напрямую

    def get_prompt_storage(self):
        """DEPRECATED: PromptStorage удалён. Используйте DataRepository."""
        raise RuntimeError("PromptStorage удалён. Используйте DataRepository для доступа к промптам.")

    def get_contract_storage(self):
        """DEPRECATED: ContractStorage удалён. Используйте DataRepository."""
        raise RuntimeError("ContractStorage удалён. Используйте DataRepository для доступа к контрактам.")

    def get_resource_discovery(self) -> ResourceDiscovery:
        """DEPRECATED: Используйте свойство resource_discovery напрямую"""
        import warnings
        warnings.warn("get_resource_discovery deprecated. Используйте self.resource_discovery напрямую", DeprecationWarning, stacklevel=2)
        if not hasattr(self, 'resource_discovery') or self.resource_discovery is None:
            raise RuntimeError("ResourceDiscovery не инициализирован")
        return self.resource_discovery

    def get_telemetry(self) -> TelemetryCollector:
        """Получение TelemetryCollector."""
        if not hasattr(self, 'telemetry') or self.telemetry is None:
            raise RuntimeError("TelemetryCollector не инициализирован")
        return self.telemetry

    def get_metrics_publisher(self) -> MetricsPublisher:
        """Получение MetricsPublisher для унифицированной публикации метрик."""
        if not hasattr(self, 'metrics_publisher') or self.metrics_publisher is None:
            raise RuntimeError("MetricsPublisher не инициализирован")
        return self.metrics_publisher

    def get_session_handler(self) -> SessionLogHandler:
        """Получение обработчика логов сессии."""
        if not hasattr(self, 'session_handler') or self.session_handler is None:
            raise RuntimeError("SessionHandler не инициализирован")
        return self.session_handler

    def get_terminal_handler(self) -> TerminalLogHandler:
        """Получение терминального обработчика."""
        if not hasattr(self, 'terminal_handler') or self.terminal_handler is None:
            raise RuntimeError("TerminalHandler не инициализирован")
        return self.terminal_handler

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
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.event_bus_logger.debug(f"Используем LLM провайдер: {provider_name}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            
                if not fallback:
                    raise ValueError(f"LLM провайдер '{provider_name}' не найден")
        
        # 2. Если не найдено, пробуем default
        if llm is None:
            llm = self._get_default_llm()
            if llm:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.event_bus_logger.debug("Используем default LLM провайдер")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        
        # 3. Если всё ещё нет, пробуем первый доступный
        if llm is None:
            llm = self._get_first_available_llm()
            if llm:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.event_bus_logger.warning("Default LLM не найден, используем первый доступный")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        
        # 4. Если вообще нет LLM → ошибка
        if llm is None:
            raise ValueError("Нет доступных LLM провайдеров")
        
        # 5. Вызов провайдера
        try:
            response = await llm.generate(request)
            return response
        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.event_bus_logger.error(f"Ошибка LLM провайдера: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            
            if fallback and provider_name:
                # Пытаемся использовать backup
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.event_bus_logger.warning("Попытка fallback на backup LLM")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                backup_llm = self._get_backup_llm(exclude_name=provider_name)
                
                if backup_llm:
                    try:
                        response = await backup_llm.generate(request)
                        return response
                    except Exception as backup_error:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        self.event_bus_logger.error(f"Backup LLM также не удался: {backup_error}")
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            
            # Если fallback не помог или не запрошен
            raise

    def _get_default_llm(self):
        """Получение default LLM провайдера."""
        for info in self.resource_registry.all():
            if info.resource_type == ResourceType.LLM and info.is_default:
                return info.instance
        return None

    def _get_first_available_llm(self):
        """Получение первого доступного LLM провайдера."""
        for info in self.resource_registry.all():
            if info.resource_type == ResourceType.LLM:
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
            if (info.resource_type == ResourceType.LLM and
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

    def get_vector_search_status(self) -> Dict[str, Any]:
        """
        Получение статуса инициализации Vector Search.
        
        ВОЗВРАЩАЕТ:
        - Dict с информацией о каждом индексе:
          {
            "books": {"status": "loaded"|"missing"|"error", "vectors": int, ...},
            ...
          }
        """
        return getattr(self, '_vector_search_status', {})

    def is_vector_search_ready(self, source: str) -> bool:
        """
        Проверка готовности Vector Search для источника.
        
        ПАРАМЕТРЫ:
        - source: Источник (books/knowledge/history/docs)
        
        ВОЗВРАЩАЕТ:
        - True если индекс загружен и содержит векторы
        """
        status = self._vector_search_status.get(source, {})
        return status.get("status") == "loaded" and status.get("vectors", 0) > 0

    async def shutdown(self):
        """Завершение работы инфраструктурного контекста."""
        if self.lifecycle_manager and self.lifecycle_manager.state == ComponentState.SHUTDOWN:
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.warning("InfrastructureContext уже завершён")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return
        
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        await self.event_bus_logger.info("Начало завершения работы InfrastructureContext")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Сохранение Vector Search индексов
        if self._faiss_providers and self.config.vector_search:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("Сохранение Vector Search индексов...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            from pathlib import Path
            for source, provider in self._faiss_providers.items():
                try:
                    index_path = Path(self.config.vector_search.storage.base_path) / f"{source}_index.faiss"
                    index_path.parent.mkdir(parents=True, exist_ok=True)
                    await provider.save(str(index_path))
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.info(f"💾 Сохранён индекс {source}: {index_path}")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(f"Ошибка сохранения индекса {source}: {e}")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        
        # Завершение Vector Search провайдеров
        for source, provider in self._faiss_providers.items():
            try:
                await provider.shutdown()
            except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"Ошибка завершения FAISS провайдера {source}: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        if self._embedding_provider:
            try:
                await self._embedding_provider.shutdown()
            except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"Ошибка завершения Embedding провайдера: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Завершение работы через менеджер жизненного цикла
        if self.lifecycle_manager:
            await self.lifecycle_manager.cleanup_all()

        # Закрытие обработчиков логирования
        if hasattr(self, 'file_handler') and self.file_handler:
            from core.infrastructure.logging import shutdown_logging
            shutdown_logging(self.file_handler)
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("Обработчики логирования закрыты")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        await self.event_bus_logger.info("InfrastructureContext завершен")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    # =============================================================================
    # ПРОВЕРКИ СОСТОЯНИЯ
    # =============================================================================
    
    @property
    def is_ready(self) -> bool:
        """Проверка готовности инфраструктурного контекста."""
        return self.lifecycle_manager is not None and self.lifecycle_manager.is_ready
    
    @property
    def is_initialized(self) -> bool:
        """Проверка, был ли контекст инициализирован."""
        return self.lifecycle_manager is not None and self.lifecycle_manager.is_initialized
    
    @property
    def is_failed(self) -> bool:
        """Проверка, завершилась ли инициализация ошибкой."""
        return self.lifecycle_manager is not None and self.lifecycle_manager.state == ComponentState.FAILED
    
    @property
    def state(self) -> ComponentState:
        """Текущее состояние инфраструктурного контекста."""
        if self.lifecycle_manager is None:
            return ComponentState.CREATED
        return self.lifecycle_manager.state
    
    def is_fully_initialized(self) -> bool:
        """Проверка полной инициализации (для обратной совместимости)."""
        return self.is_ready