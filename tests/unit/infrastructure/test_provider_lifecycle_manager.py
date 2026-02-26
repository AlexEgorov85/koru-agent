"""
Тесты для Provider Lifecycle Manager.

TESTS:
- test_register_provider: Регистрация провайдера
- test_unregister_provider: Удаление провайдера
- test_initialize_all: Инициализация всех провайдеров
- test_shutdown_all: Завершение работы всех провайдеров
- test_health_check_all: Проверка здоровья всех провайдеров
- test_provider_order: Порядок инициализации/shutdown
- test_duplicate_registration: Дублирование регистрации
- test_get_provider: Получение провайдера по имени
- test_get_providers_by_type: Получение провайдеров по типу
- test_lifecycle_stats: Статистика lifecycle
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.providers import (
    ProviderLifecycleManager,
    ProviderType,
    ProviderHealthStatus,
    BaseProvider,
    get_lifecycle_manager,
    reset_lifecycle_manager,
)
from core.infrastructure.event_bus import reset_event_bus_manager


class MockProvider(BaseProvider):
    """Mock провайдер для тестов."""
    
    def __init__(self, name: str, config: dict = None):
        super().__init__(name, config)
        self.initialize_called = False
        self.shutdown_called = False
        self.health_check_called = False
        self.fail_initialize = False
        self.fail_health_check = False
    
    async def initialize(self) -> bool:
        self.initialize_called = True
        if self.fail_initialize:
            raise Exception("Initialization failed")
        return await super().initialize()
    
    async def shutdown(self) -> None:
        self.shutdown_called = True
        await super().shutdown()
    
    async def health_check(self) -> dict:
        self.health_check_called = True
        if self.fail_health_check:
            raise Exception("Health check failed")
        return await super().health_check()


@pytest.fixture
def lifecycle_manager():
    """Фикстура: новый менеджер lifecycle для каждого теста."""
    reset_lifecycle_manager()
    reset_event_bus_manager()
    manager = ProviderLifecycleManager()
    yield manager
    reset_lifecycle_manager()
    reset_event_bus_manager()


@pytest.fixture
def mock_providers():
    """Фикстура: набор mock провайдеров."""
    return {
        "llm": MockProvider("test_llm"),
        "database": MockProvider("test_db"),
        "vector": MockProvider("test_vector"),
    }


class TestProviderRegistration:
    """Тесты регистрации провайдеров."""

    @pytest.mark.asyncio
    async def test_register_provider(self, lifecycle_manager):
        """Регистрация провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register(
            name="test_provider",
            provider=provider,
            provider_type=ProviderType.LLM,
        )
        
        assert lifecycle_manager.providers_count == 1
        assert lifecycle_manager.get_provider("test_provider") is provider
        
        provider_info = lifecycle_manager.get_provider_info("test_provider")
        assert provider_info.name == "test_provider"
        assert provider_info.provider_type == ProviderType.LLM

    @pytest.mark.asyncio
    async def test_duplicate_registration(self, lifecycle_manager):
        """Попытка дублирования регистрации."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        
        with pytest.raises(ValueError, match="уже зарегистрирован"):
            await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)

    @pytest.mark.asyncio
    async def test_unregister_provider(self, lifecycle_manager):
        """Удаление провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        assert lifecycle_manager.providers_count == 1
        
        result = await lifecycle_manager.unregister("test_provider")
        
        assert result is True
        assert lifecycle_manager.providers_count == 0
        assert lifecycle_manager.get_provider("test_provider") is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self, lifecycle_manager):
        """Удаление несуществующего провайдера."""
        result = await lifecycle_manager.unregister("nonexistent")
        assert result is False


class TestProviderInitialization:
    """Тесты инициализации провайдеров."""

    @pytest.mark.asyncio
    async def test_initialize_single_provider(self, lifecycle_manager):
        """Инициализация одного провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        results = await lifecycle_manager.initialize_all()
        
        assert results["test_provider"] is True
        assert provider.initialize_called is True
        assert provider.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_all(self, lifecycle_manager, mock_providers):
        """Инициализация всех провайдеров."""
        for name, provider in mock_providers.items():
            provider_type = getattr(ProviderType, name.upper())
            await lifecycle_manager.register(name, provider, provider_type)
        
        results = await lifecycle_manager.initialize_all()
        
        assert len(results) == 3
        assert all(results.values())
        assert all(p.initialize_called for p in mock_providers.values())

    @pytest.mark.asyncio
    async def test_initialize_failed_provider(self, lifecycle_manager):
        """Инициализация провайдера с ошибкой."""
        provider = MockProvider("test_provider")
        provider.fail_initialize = True
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        results = await lifecycle_manager.initialize_all()
        
        assert results["test_provider"] is False
        assert provider.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_twice(self, lifecycle_manager):
        """Двойная инициализация."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        await lifecycle_manager.initialize_all()
        await lifecycle_manager.initialize_all()
        
        # Вторая инициализация должна пройти успешно
        assert provider.is_initialized is True


class TestProviderShutdown:
    """Тесты завершения работы провайдеров."""

    @pytest.mark.asyncio
    async def test_shutdown_single_provider(self, lifecycle_manager):
        """Завершение работы одного провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        await lifecycle_manager.initialize_all()
        results = await lifecycle_manager.shutdown_all()
        
        assert results["test_provider"] is True
        assert provider.shutdown_called is True
        assert provider.is_initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_all(self, lifecycle_manager, mock_providers):
        """Завершение работы всех провайдеров."""
        for name, provider in mock_providers.items():
            provider_type = getattr(ProviderType, name.upper())
            await lifecycle_manager.register(name, provider, provider_type)
        
        await lifecycle_manager.initialize_all()
        results = await lifecycle_manager.shutdown_all()
        
        assert len(results) == 3
        assert all(results.values())
        assert all(p.shutdown_called for p in mock_providers.values())

    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, lifecycle_manager):
        """Завершение работы неинициализированного провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        results = await lifecycle_manager.shutdown_all()
        
        assert results["test_provider"] is True
        assert provider.shutdown_called is False  # Не вызывался т.к. не инициализирован


class TestHealthCheck:
    """Тесты проверки здоровья."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, lifecycle_manager):
        """Проверка здорового провайдера."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        await lifecycle_manager.initialize_all()
        
        results = await lifecycle_manager.health_check_all()
        
        assert "test_provider" in results
        assert results["test_provider"].is_healthy is True
        assert results["test_provider"].status == ProviderHealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_failed(self, lifecycle_manager):
        """Проверка провайдера с ошибкой health check."""
        provider = MockProvider("test_provider")
        provider.fail_health_check = True
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        
        results = await lifecycle_manager.health_check_all()
        
        assert results["test_provider"].is_healthy is False
        assert results["test_provider"].status == ProviderHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_all(self, lifecycle_manager, mock_providers):
        """Проверка здоровья всех провайдеров."""
        for name, provider in mock_providers.items():
            provider_type = getattr(ProviderType, name.upper())
            await lifecycle_manager.register(name, provider, provider_type)
        
        await lifecycle_manager.initialize_all()
        results = await lifecycle_manager.health_check_all()
        
        assert len(results) == 3
        assert all(r.is_healthy for r in results.values())


class TestProviderOrdering:
    """Тесты порядка инициализации/shutdown."""

    @pytest.mark.asyncio
    async def test_initialization_order(self, lifecycle_manager):
        """Проверка порядка инициализации (по типам)."""
        init_order = []
        
        class TrackedProvider(MockProvider):
            async def initialize(self) -> bool:
                init_order.append(self.name)
                return await super().initialize()
        
        # Регистрируем в разном порядке
        await lifecycle_manager.register("llm", TrackedProvider("llm"), ProviderType.LLM)
        await lifecycle_manager.register("db", TrackedProvider("db"), ProviderType.DATABASE)
        await lifecycle_manager.register("vector", TrackedProvider("vector"), ProviderType.VECTOR)
        
        await lifecycle_manager.initialize_all()
        
        # DATABASE должен инициализироваться раньше LLM
        db_index = init_order.index("db")
        llm_index = init_order.index("llm")
        assert db_index < llm_index

    @pytest.mark.asyncio
    async def test_shutdown_order(self, lifecycle_manager):
        """Проверка порядка shutdown (обратный инициализации)."""
        shutdown_order = []
        
        class TrackedProvider(MockProvider):
            async def shutdown(self) -> None:
                shutdown_order.append(self.name)
                await super().shutdown()
        
        await lifecycle_manager.register("llm", TrackedProvider("llm"), ProviderType.LLM)
        await lifecycle_manager.register("database", TrackedProvider("database"), ProviderType.DATABASE)
        
        await lifecycle_manager.initialize_all()
        await lifecycle_manager.shutdown_all()
        
        # Порядок shutdown: LLM -> STORAGE -> EMBEDDING -> VECTOR -> CACHE -> DATABASE
        # DATABASE инициализируется первым, завершается последним
        llm_index = shutdown_order.index("llm")
        db_index = shutdown_order.index("database")
        # LLM завершается раньше DATABASE
        assert llm_index < db_index


class TestProviderQueries:
    """Тесты получения провайдеров."""

    @pytest.mark.asyncio
    async def test_get_provider(self, lifecycle_manager):
        """Получение провайдера по имени."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        
        result = lifecycle_manager.get_provider("test_provider")
        assert result is provider
        
        result_none = lifecycle_manager.get_provider("nonexistent")
        assert result_none is None

    @pytest.mark.asyncio
    async def test_get_providers_by_type(self, lifecycle_manager):
        """Получение провайдеров по типу."""
        llm1 = MockProvider("llm1")
        llm2 = MockProvider("llm2")
        db = MockProvider("db")
        
        await lifecycle_manager.register("llm1", llm1, ProviderType.LLM)
        await lifecycle_manager.register("llm2", llm2, ProviderType.LLM)
        await lifecycle_manager.register("db", db, ProviderType.DATABASE)
        
        llm_providers = lifecycle_manager.get_providers_by_type(ProviderType.LLM)
        
        assert len(llm_providers) == 2
        assert llm1 in llm_providers
        assert llm2 in llm_providers
        assert db not in llm_providers


class TestLifecycleStats:
    """Тесты статистики lifecycle."""

    @pytest.mark.asyncio
    async def test_get_all_stats(self, lifecycle_manager, mock_providers):
        """Получение полной статистики."""
        for name, provider in mock_providers.items():
            provider_type = getattr(ProviderType, name.upper())
            await lifecycle_manager.register(name, provider, provider_type)
        
        await lifecycle_manager.initialize_all()
        
        stats = lifecycle_manager.get_all_stats()
        
        assert stats["total_providers"] == 3
        assert stats["initialized_count"] == 3
        assert stats["healthy_count"] == 3
        assert "providers" in stats
        assert "llm" in stats["providers"]

    @pytest.mark.asyncio
    async def test_initialized_count_property(self, lifecycle_manager):
        """Проверка свойства initialized_count."""
        provider = MockProvider("test_provider")
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        
        assert lifecycle_manager.initialized_count == 0
        
        await lifecycle_manager.initialize_all()
        
        assert lifecycle_manager.initialized_count == 1

    @pytest.mark.asyncio
    async def test_is_initialized_property(self, lifecycle_manager):
        """Проверка свойства is_initialized."""
        provider = MockProvider("test_provider")
        
        assert lifecycle_manager.is_initialized is False
        
        await lifecycle_manager.register("test_provider", provider, ProviderType.LLM)
        await lifecycle_manager.initialize_all()
        
        assert lifecycle_manager.is_initialized is True


class TestSingleton:
    """Тесты singleton паттерна."""

    def test_get_lifecycle_manager_singleton(self):
        """get_lifecycle_manager возвращает тот же экземпляр."""
        reset_lifecycle_manager()
        
        manager1 = get_lifecycle_manager()
        manager2 = get_lifecycle_manager()
        
        assert manager1 is manager2

    def test_reset_lifecycle_manager(self):
        """Сброс singleton для тестов."""
        reset_lifecycle_manager()
        manager1 = get_lifecycle_manager()
        
        reset_lifecycle_manager()
        manager2 = get_lifecycle_manager()
        
        assert manager1 is not manager2
