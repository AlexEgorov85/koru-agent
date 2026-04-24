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
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from core.infrastructure.providers.llm.llama_cpp_provider import MockLlamaCppConfig
from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
from core.infrastructure.providers.llm.openrouter_provider import OpenRouterConfig
from core.infrastructure.providers.llm.vllm_provider import VLLMConfig
from core.infrastructure_context.lifecycle_manager import LifecycleManager
from core.infrastructure_context.resource_registry import ResourceRegistry
from core.components.services.metrics_publisher import MetricsPublisher

from core.models.enums.component_status import ComponentStatus
from core.config.app_config import AppConfig
from core.config.logging_config import LoggingConfig
from core.infrastructure.logging.session import LoggingSession
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.providers.llm.factory import LLMProviderFactory
from core.infrastructure.providers.database.factory import DBProviderFactory
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.models.data.resource import ResourceInfo
from core.models.enums.common_enums import ResourceType
from core.infrastructure.loading.resource_loader import ResourceLoader

# Импорты для телеметрии
from core.infrastructure.telemetry.handlers.session_handler import SessionLogHandler
from core.infrastructure.telemetry.storage.metrics_storage import FileSystemMetricsStorage


class InfrastructureContext:
    """Главный класс инфраструктурного контекста. Создаётся 1 раз за жизненный цикл приложения."""

    def __init__(
        self,
        config: AppConfig,
        logging_config: Optional[LoggingConfig] = None
    ):
        """
        Инициализация инфраструктурного контекста.

        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (AppConfig)
        - logging_config: Конфигурация логирования (опционально, создаст дефолтную если None)
        """
        self.id = str(uuid.uuid4())
        self.config = config

        # Сессия логирования (создаётся один раз, управляет всеми файлами логов)
        self.log_session = LoggingSession(logging_config or LoggingConfig())
        # Логгер инфраструктуры (будет инициализирован после setup_context_loggers)
        self.log: Optional[logging.Logger] = None

        # Основные компоненты инфраструктуры
        self.lifecycle_manager: Optional[LifecycleManager] = None
        # Шина событий: UnifiedEventBus или EventBusConcurrent в зависимости от флага
        self.event_bus: Optional[UnifiedEventBus] = None
        self.resource_registry: Optional[ResourceRegistry] = None

        # Фабрики провайдеров
        self.llm_provider_factory: Optional[LLMProviderFactory] = None
        self.db_provider_factory: Optional[DBProviderFactory] = None

        # Инфраструктурные хранилища (только загрузка, без кэширования)
        self.resource_loader: Optional[ResourceLoader] = None  # ЕДИНЫЙ загрузчик ресурсов

        # Хранилище метрик
        self.metrics_storage: Optional[IMetricsStorage] = None

        # Обработчик логов сессии
        self.session_handler: Optional[SessionLogHandler] = None

        # MetricsPublisher для унифицированной публикации метрик
        self.metrics_publisher: Optional[MetricsPublisher] = None

        # Vector Search провайдеры
        self._faiss_providers: Dict[str, Any] = {}
        self._embedding_provider: Optional[Any] = None
        self._chunking_strategy: Optional[Any] = None

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
            self.log.warning("InfrastructureContext уже инициализирован",
                             extra={"event_type": LogEventType.WARNING})
            return True

        # Проверка на предыдущую ошибку
        if self.lifecycle_manager and self.lifecycle_manager.state == ComponentStatus.FAILED:
            self.log.error("InfrastructureContext в состоянии FAILED",
                           extra={"event_type": LogEventType.SYSTEM_ERROR})
            return False

        # === ЭТАП 1: Базовая инициализация ===
        # Логгер ещё не создан — используем стандартный logging напрямую
        _init_logger = logging.getLogger(__name__)
        _init_logger.info("🚀 Инициализация инфраструктурного контекста...")

        # Настройка файловой системы логов (создаёт директорию и файлы контекстов)
        self.log_session.setup_context_loggers()
        self.log = self.log_session.infra_logger
        self.log.info("🚀 Инициализация инфраструктуры...",
                      extra={"event_type": LogEventType.SYSTEM_INIT})

        # Инициализация шины событий (ПЕРВЫЙ компонент)
        self.event_bus = UnifiedEventBus()
        self.log.info("Инициализирована шина событий: UnifiedEventBus",
                      extra={"event_type": LogEventType.SYSTEM_INIT})

        # === Инициализация обработкторов (вместо TelemetryCollector) ===
        from pathlib import Path

        storage_dir = Path(self.config.data_dir)

        # 1. SessionLogHandler — запись логов сессий в файлы
        self.session_handler = SessionLogHandler(
            event_bus=self.event_bus,
            base_log_dir=storage_dir / "logs" / "sessions"
        )
        self.log.info("SessionLogHandler инициализирован",
                      extra={"event_type": LogEventType.SYSTEM_INIT})

        # 2. MetricsPublisher — сбор метрик
        metrics_storage = FileSystemMetricsStorage(storage_dir / "metrics")
        self.metrics_publisher = MetricsPublisher(metrics_storage, self.event_bus)

        # Подписка на события метрик
        self.event_bus.subscribe(EventType.SKILL_EXECUTED, self._on_skill_executed)
        self.event_bus.subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
        self.event_bus.subscribe(EventType.SESSION_STARTED, self._on_session_started)
        self.event_bus.subscribe(EventType.SESSION_COMPLETED, self._on_session_completed)
        self.log.info("MetricsPublisher инициализирован",
                      extra={"event_type": LogEventType.SYSTEM_INIT})

        # Инициализация менеджера жизненного цикла
        from core.infrastructure_context.lifecycle_manager import LifecycleManager
        self.lifecycle_manager = LifecycleManager(self.event_bus, log=self.log)

        # Инициализация реестра ресурсов
        self.resource_registry = ResourceRegistry()

        # === ЭТАП 2: Фабрики провайдеров ===
        self.llm_provider_factory = LLMProviderFactory()
        self.db_provider_factory = DBProviderFactory()

        # === ЭТАП 3: Инфраструктурные хранилища ===
        from pathlib import Path

        # === ЭТАП 3.5: ResourceLoader (ЕДИНЫЙ загрузчик) ===
        self.log.info("=== ЭТАП 3.5: ResourceLoader — загрузка промптов и контрактов ===",
                      extra={"event_type": LogEventType.SYSTEM_INIT})
        import asyncio
        data_dir = Path(self.config.data_dir)
        self.resource_loader = ResourceLoader.get(
            data_dir=data_dir,
            profile=self.config.profile,
            logger=self.log,
        )
        await asyncio.to_thread(self.resource_loader.load_all)

        # === ЭТАП 4: Метрики (уже инициализированы в telemetry) ===
        # Доступ через self.telemetry.metrics_publisher

        # === ЭТАП 5: Vector Search ===
        # Инициализация Vector Search
        if self.config.vector_search and self.config.vector_search.enabled:
            await self._init_vector_search()

        # === ЭТАП 6: Регистрация провайдеров через LifecycleManager ===
        # Вызываем регистрацию провайдеров через LifecycleManager
        try:
            self.log.info("=== ЭТАП 6: Регистрация провайдеров через LifecycleManager ===",
                          extra={"event_type": LogEventType.SYSTEM_INIT})
            await self._register_providers_from_config()

            # Инициализация всех зарегистрированных провайдеров через LifecycleManager
            self.log.info("Вызов lifecycle_manager.initialize_all()...",
                          extra={"event_type": LogEventType.SYSTEM_INIT})
            await self.lifecycle_manager.initialize_all()
            self.log.info("[OK] LifecycleManager initialized",
                          extra={"event_type": LogEventType.SYSTEM_READY})
        except Exception as e:
            self.log.error("[ERROR] Provider init error: %s", str(e),
                           extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)
            return False

        await self.event_bus.publish(
            EventType.USER_RESULT,
            data={"message": "InfrastructureContext initialized", "icon": "[OK]"},
            session_id=str(self.id),
        )
        return True

    async def _register_providers_from_config(self):
        """Регистрация провайдеров из конфигурации."""
        has_llm = hasattr(self.config, 'llm_providers')
        if has_llm and self.config.llm_providers:
            for name, prov in self.config.llm_providers.items():
                self.log.info("[LLM] - %s: enabled=%s, type=%s",
                              name, prov.enabled, prov.provider_type,
                              extra={"event_type": LogEventType.SYSTEM_INIT})

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
                            config=config_obj,
                            log_session=self.log_session
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
                        self.log.error("[LLM] Ошибка регистрации провайдера '%s': %s",
                                       provider_name, str(e),
                                       extra={"event_type": LogEventType.LLM_ERROR}, exc_info=True)
                        raise

        # Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    # Create appropriate config based on provider type
                    provider_type = getattr(provider_config, 'provider_type', getattr(provider_config, 'type_provider', None))
                    
                    # Выбираем класс конфигурации в зависимости от типа БД
                    from core.models.types.db_types import DBConnectionConfig
                    config_obj = DBConnectionConfig(**provider_config.parameters)

                    provider = self.db_provider_factory.create_provider(
                        provider_type=provider_type,
                        config=config_obj,
                        log_session=self.log_session
                    )

                    # Регистрация в LifecycleManager
                    db_info = {
                        "provider_type": provider_type,
                        "database": provider_config.parameters.get("database", ""),
                        "host": provider_config.parameters.get("host", "localhost"),
                        "port": provider_config.parameters.get("port", 5432),
                    }
                    
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
                    self.log.error("[ERROR] DB provider registration error '%s': %s",
                                   provider_name, str(e),
                                   extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)

    async def _init_vector_search(self):
        """Инициализация векторного поиска с проверкой наличия индексов."""
        from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
        from pathlib import Path

        vs_config = self.config.vector_search
        self.log.info("Инициализация Vector Search...",
                      extra={"event_type": LogEventType.SYSTEM_INIT})

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
                    self.log.info("[OK] Loaded index %s: %s (%d vectors)",
                                  source, index_path, count,
                                  extra={"event_type": LogEventType.SYSTEM_INIT})
                else:
                    indexes_status[source] = {
                        "status": "missing",
                        "path": str(index_path),
                        "vectors": 0
                    }
                    self.log.warning("[WARN] Index %s not found: %s. Indexing required.",
                                 source, index_path,
                                 extra={"event_type": LogEventType.WARNING})

                self._faiss_providers[source] = provider
            except Exception as e:
                indexes_status[source] = {
                    "status": "error",
                    "error": str(e)
                }
                self.log.error("[ERROR] FAISS provider init error %s: %s",
                               source, str(e),
                               extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)
                continue

        # Логирование общего статуса
        total_vectors = sum(s.get("vectors", 0) for s in indexes_status.values())
        loaded_count = sum(1 for s in indexes_status.values() if s.get("status") == "loaded")
        missing_count = sum(1 for s in indexes_status.values() if s.get("status") == "missing")

        self.log.info("Vector Search статус: %d загружено, %d отсутствует, всего векторов: %d",
                      loaded_count, missing_count, total_vectors,
                      extra={"event_type": LogEventType.SYSTEM_INIT})

        # Инициализация Embedding провайдера
        try:
            model_name = vs_config.embedding.model_name
            if "Giga-Embeddings" in model_name or "giga" in model_name.lower():
                from core.infrastructure.providers.embedding.giga_embeddings_provider import GigaEmbeddingsProvider
                self._embedding_provider = GigaEmbeddingsProvider(vs_config.embedding)
            else:
                from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
                self._embedding_provider = SentenceTransformersProvider(vs_config.embedding)
            
            await self._embedding_provider.initialize()
            self.log.info("[OK] Embedding initialized: %s",
                          vs_config.embedding.model_name,
                          extra={"event_type": LogEventType.SYSTEM_INIT})
        except Exception as e:
            self.log.error("Ошибка инициализации Embedding провайдера: %s",
                           str(e),
                           extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)

        # Инициализация Chunking стратегии
        try:
            self._chunking_strategy = TextChunkingStrategy(
                chunk_size=vs_config.chunking.chunk_size,
                chunk_overlap=vs_config.chunking.chunk_overlap,
                min_chunk_size=vs_config.chunking.min_chunk_size
            )
            self.log.info("[OK] Chunking initialized: %d chars",
                          vs_config.chunking.chunk_size,
                          extra={"event_type": LogEventType.SYSTEM_INIT})
        except Exception as e:
            self.log.error("Ошибка инициализации Chunking стратегии: %s",
                           str(e),
                           extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)

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
                    self.log.info("Провайдер '%s' завершен",
                                  provider_name,
                                  extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
            except Exception as e:
                self.log.error("Ошибка при завершении провайдера '%s': %s",
                               provider_name, str(e),
                               extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)

        # Завершение работы хранилищ
        if self.prompt_storage and hasattr(self.prompt_storage, 'shutdown'):
            await self.prompt_storage.shutdown()
        if self.contract_storage and hasattr(self.contract_storage, 'shutdown'):
            await self.contract_storage.shutdown()

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

    def get_resource_loader(self) -> ResourceLoader:
        """Получение загрузчика ресурсов."""
        if self.resource_loader is None:
            raise RuntimeError("ResourceLoader не инициализирован")
        return self.resource_loader

    def get_session_handler(self) -> SessionLogHandler:
        """Получение обработчика логов сессии."""
        if not hasattr(self, 'session_handler') or self.session_handler is None:
            raise RuntimeError("SessionHandler не инициализирован")
        return self.session_handler

    def get_metrics_publisher(self) -> MetricsPublisher:
        """Получение MetricsPublisher для унифицированной публикации метрик."""
        if not hasattr(self, 'metrics_publisher') or self.metrics_publisher is None:
            raise RuntimeError("MetricsPublisher не инициализирован")
        return self.metrics_publisher

    # === Обработчики метрик (перенесены из TelemetryCollector) ===

    async def _on_skill_executed(self, event):
        """Обработка выполнения навыка."""
        data = event.data
        if not data.get('capability') or not self.metrics_publisher:
            return
        success = 1.0 if data.get('success', False) else 0.0
        await self.metrics_publisher.gauge(
            name='success', value=success,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            version=data.get('version'),
            timestamp=event.timestamp,
            publish_event=False
        )
        execution_time = data.get('execution_time_ms')
        if execution_time:
            await self.metrics_publisher.histogram(
                name='execution_time_ms', value=float(execution_time),
                agent_id=data.get('agent_id', 'unknown'),
                capability=data.get('capability'),
                session_id=data.get('session_id'),
                correlation_id=event.correlation_id,
                version=data.get('version'),
                timestamp=event.timestamp,
                publish_event=False
            )
        tokens = data.get('tokens_used')
        if tokens:
            await self.metrics_publisher.counter(
                name='tokens_used', value=float(tokens),
                agent_id=data.get('agent_id', 'unknown'),
                capability=data.get('capability'),
                session_id=data.get('session_id'),
                correlation_id=event.correlation_id,
                version=data.get('version'),
                timestamp=event.timestamp,
                publish_event=False
            )

    async def _on_capability_selected(self, event):
        """Обработка выбора способности."""
        data = event.data
        if not data.get('capability') or not self.metrics_publisher:
            return
        await self.metrics_publisher.counter(
            name='selection_count', value=1.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            version=data.get('version'),
            timestamp=event.timestamp,
            publish_event=False
        )

    async def _on_error_occurred(self, event):
        """Обработка ошибки."""
        data = event.data
        if not data.get('capability') or not self.metrics_publisher:
            return
        error_type = data.get('error_type', 'unknown')
        await self.metrics_publisher.gauge(
            name='success', value=0.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            tags={'error': error_type},
            publish_event=False
        )
        await self.metrics_publisher.counter(
            name='error_count', value=1.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            tags={'error': error_type},
            publish_event=False
        )

    async def _on_session_started(self, event):
        """Обработка начала сессии."""
        pass

    async def _on_session_completed(self, event):
        """Обработка завершения сессии."""
        data = event.data
        steps = data.get('steps_completed', 0)
        if self.metrics_publisher:
            await self.metrics_publisher.gauge(
                name='session_steps_completed', value=float(steps),
                agent_id=data.get('agent_id', 'unknown'),
                session_id=data.get('session_id'),
                tags={'final_status': data.get('final_status', 'unknown')},
                publish_event=False
            )

    def __setattr__(self, name, value):
        """Запрет на изменение после инициализации."""
        if hasattr(self, '_initialized') and self._initialized and name != '_initialized':
            raise AttributeError("InfrastructureContext is immutable after initialization")
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
                self.log.debug("Используем LLM провайдер: %s",
                               provider_name,
                               extra={"event_type": LogEventType.LLM_CALL})

                if not fallback:
                    raise ValueError("LLM провайдер '%s' не найден" % provider_name)

        # 2. Если не найдено, пробуем default
        if llm is None:
            llm = self._get_default_llm()
            if llm:
                self.log.debug("Используем default LLM провайдер",
                               extra={"event_type": LogEventType.LLM_CALL})

        # 3. Если всё ещё нет, пробуем первый доступный
        if llm is None:
            llm = self._get_first_available_llm()
            if llm:
                self.log.warning("Default LLM не найден, используем первый доступный",
                                 extra={"event_type": LogEventType.WARNING})

        # 4. Если вообще нет LLM → ошибка
        if llm is None:
            raise ValueError("Нет доступных LLM провайдеров")

        # 5. Вызов провайдера
        try:
            response = await llm.generate(request)
            return response
        except Exception as e:
            self.log.error("Ошибка LLM провайдера: %s", str(e),
                           extra={"event_type": LogEventType.LLM_ERROR}, exc_info=True)

            if fallback and provider_name:
                # Пытаемся использовать backup
                self.log.warning("Попытка fallback на backup LLM",
                                 extra={"event_type": LogEventType.WARNING})
                backup_llm = self._get_backup_llm(exclude_name=provider_name)

                if backup_llm:
                    try:
                        response = await backup_llm.generate(request)
                        return response
                    except Exception as backup_error:
                        self.log.error("Backup LLM также не удался: %s", str(backup_error),
                                       extra={"event_type": LogEventType.LLM_ERROR}, exc_info=True)

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
        if self.lifecycle_manager and self.lifecycle_manager.state == ComponentStatus.SHUTDOWN:
            self.log.warning("InfrastructureContext уже завершён",
                             extra={"event_type": LogEventType.WARNING})
            return

        self.log.info("Начало завершения работы InfrastructureContext",
                      extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})

        # Завершение Vector Search провайдеров
        for source, provider in self._faiss_providers.items():
            try:
                await provider.shutdown()
            except Exception as e:
                self.log.error("Ошибка завершения FAISS провайдера %s: %s",
                               source, str(e),
                               extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)

        if self._embedding_provider:
            try:
                await self._embedding_provider.shutdown()
            except Exception as e:
                self.log.error("Ошибка завершения Embedding провайдера: %s",
                               str(e),
                               extra={"event_type": LogEventType.SYSTEM_ERROR}, exc_info=True)

        # Завершение работы через менеджер жизненного цикла
        if self.lifecycle_manager:
            await self.lifecycle_manager.cleanup_all()

        # Отписка от EventBus (метрики)
        if self.event_bus:
            for event_type in [EventType.SKILL_EXECUTED, EventType.CAPABILITY_SELECTED,
                               EventType.ERROR_OCCURRED, EventType.SESSION_STARTED,
                               EventType.SESSION_COMPLETED]:
                try:
                    if hasattr(self.event_bus, 'unsubscribe'):
                        self.event_bus.unsubscribe(event_type)
                except Exception:
                    pass

        # Закрытие SessionLogHandler
        if self.session_handler:
            await self.session_handler.shutdown()

        # Закрытие сессии логирования
        self.log_session.shutdown()

        self.log.info("InfrastructureContext завершён",
                      extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
    
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
        return self.lifecycle_manager is not None and self.lifecycle_manager.state == ComponentStatus.FAILED
    
    @property
    def state(self) -> ComponentStatus:
        """Текущее состояние инфраструктурного контекста."""
        if self.lifecycle_manager is None:
            return ComponentStatus.CREATED
        return self.lifecycle_manager.state
    
    def is_fully_initialized(self) -> bool:
        """Проверка полной инициализации (для обратной совместимости)."""
        return self.is_ready