"""
Тесты для Lifecycle Manager.

TESTS:
- Регистрация ресурсов
- Инициализация с учётом зависимостей
- Завершение работы в обратном порядке
- Проверка здоровья
- Топологическая сортировка
- Статистика и информация о ресурсах
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.context.lifecycle_manager import (
    LifecycleManager,
    ResourceType,
    ResourceStatus,
    ResourceRecord,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus


class MockResource:
    """Mock ресурс для тестов."""

    def __init__(self, name: str, fail_initialize: bool = False, fail_shutdown: bool = False, fail_health_check: bool = False):
        self.name = name
        self.fail_initialize = fail_initialize
        self.fail_shutdown = fail_shutdown
        self.fail_health_check = fail_health_check
        self.initialize_called = False
        self.shutdown_called = False
        self.health_check_called = False
        self.is_initialized = False

    async def initialize(self) -> bool:
        self.initialize_called = True
        if self.fail_initialize:
            raise Exception("Initialization failed")
        self.is_initialized = True
        return True

    async def shutdown(self) -> None:
        self.shutdown_called = True
        self.is_initialized = False

    async def health_check(self) -> dict:
        self.health_check_called = True
        if self.fail_health_check:
            raise Exception("Health check failed")
        return {
            "status": "healthy" if self.is_initialized else "unhealthy",
            "name": self.name,
        }

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "initialized": self.is_initialized,
        }


@pytest.fixture
def event_bus():
    """Фикстура: шина событий."""
    return UnifiedEventBus()


@pytest.fixture
def lifecycle_manager(event_bus):
    """Фикстура: новый менеджер lifecycle для каждого теста."""
    manager = LifecycleManager(event_bus)
    yield manager


@pytest.fixture
def mock_resources():
    """Фикстура: набор mock ресурсов."""
    return {
        "llm": MockResource("test_llm"),
        "database": MockResource("test_db"),
        "storage": MockResource("test_storage"),
    }


class TestResourceRegistration:
    """Тесты регистрации ресурсов."""

    @pytest.mark.asyncio
    async def test_register_resource(self, lifecycle_manager):
        """Регистрация ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            name="test_resource",
            resource=resource,
            resource_type=ResourceType.LLM,
        )

        assert lifecycle_manager.resources_count == 1
        assert lifecycle_manager.get_resource("test_resource") is resource

        record = lifecycle_manager.get_resource_record("test_resource")
        assert record.name == "test_resource"
        assert record.resource_type == ResourceType.LLM

    @pytest.mark.asyncio
    async def test_duplicate_registration(self, lifecycle_manager):
        """Попытка дублирования регистрации."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )

        with pytest.raises(ValueError, match="already registered"):
            await lifecycle_manager.register_resource(
                "test_resource", resource, ResourceType.LLM
            )

    @pytest.mark.asyncio
    async def test_register_with_dependencies(self, lifecycle_manager):
        """Регистрация ресурса с зависимостями."""
        db_resource = MockResource("database")
        llm_resource = MockResource("llm")

        await lifecycle_manager.register_resource(
            "database", db_resource, ResourceType.DATABASE
        )
        await lifecycle_manager.register_resource(
            "llm", llm_resource, ResourceType.LLM, dependencies=["database"]
        )

        record = lifecycle_manager.get_resource_record("llm")
        assert record.dependencies == ["database"]


class TestResourceInitialization:
    """Тесты инициализации ресурсов."""

    @pytest.mark.asyncio
    async def test_initialize_single_resource(self, lifecycle_manager):
        """Инициализация одного ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        results = await lifecycle_manager.initialize_all()

        assert results["test_resource"] is True
        assert resource.initialize_called is True
        assert resource.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_all(self, lifecycle_manager, mock_resources):
        """Инициализация всех ресурсов."""
        for name, resource in mock_resources.items():
            resource_type = getattr(ResourceType, name.upper() if name != "storage" else "STORAGE")
            await lifecycle_manager.register_resource(name, resource, resource_type)

        results = await lifecycle_manager.initialize_all()

        assert len(results) == 3
        assert all(results.values())
        assert all(r.initialize_called for r in mock_resources.values())

    @pytest.mark.asyncio
    async def test_initialize_failed_resource(self, lifecycle_manager):
        """Инициализация ресурса с ошибкой."""
        resource = MockResource("test_resource", fail_initialize=True)

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        results = await lifecycle_manager.initialize_all()

        assert results["test_resource"] is False
        assert resource.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_with_dependencies(self, lifecycle_manager):
        """Инициализация с зависимостями."""
        db_resource = MockResource("database")
        llm_resource = MockResource("llm")

        await lifecycle_manager.register_resource(
            "database", db_resource, ResourceType.DATABASE
        )
        await lifecycle_manager.register_resource(
            "llm", llm_resource, ResourceType.LLM, dependencies=["database"]
        )

        results = await lifecycle_manager.initialize_all()

        assert results["database"] is True
        assert results["llm"] is True
        # database должен инициализироваться раньше llm
        assert db_resource.initialize_called
        assert llm_resource.initialize_called

    @pytest.mark.asyncio
    async def test_initialize_dependency_failed(self, lifecycle_manager):
        """Инициализация при неудачной зависимости."""
        db_resource = MockResource("database", fail_initialize=True)
        llm_resource = MockResource("llm")

        await lifecycle_manager.register_resource(
            "database", db_resource, ResourceType.DATABASE
        )
        await lifecycle_manager.register_resource(
            "llm", llm_resource, ResourceType.LLM, dependencies=["database"]
        )

        results = await lifecycle_manager.initialize_all()

        assert results["database"] is False
        assert results["llm"] is False  # LLM не инициализирован из-за failed зависимости


class TestCircularDependency:
    """Тесты циклических зависимостей."""

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, lifecycle_manager):
        """Обнаружение циклической зависимости."""
        resource_a = MockResource("resource_a")
        resource_b = MockResource("resource_b")

        # A зависит от B, B зависит от A → цикл
        await lifecycle_manager.register_resource(
            "resource_a", resource_a, ResourceType.OTHER, dependencies=["resource_b"]
        )
        await lifecycle_manager.register_resource(
            "resource_b", resource_b, ResourceType.OTHER, dependencies=["resource_a"]
        )

        with pytest.raises(RuntimeError, match="Circular dependency"):
            await lifecycle_manager.initialize_all()


class TestResourceShutdown:
    """Тесты завершения работы ресурсов."""

    @pytest.mark.asyncio
    async def test_shutdown_single_resource(self, lifecycle_manager):
        """Завершение работы одного ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        await lifecycle_manager.initialize_all()
        results = await lifecycle_manager.shutdown_all()

        assert results["test_resource"] is True
        assert resource.shutdown_called is True
        assert resource.is_initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_all(self, lifecycle_manager, mock_resources):
        """Завершение работы всех ресурсов."""
        for name, resource in mock_resources.items():
            resource_type = getattr(ResourceType, name.upper() if name != "storage" else "STORAGE")
            await lifecycle_manager.register_resource(name, resource, resource_type)

        await lifecycle_manager.initialize_all()
        results = await lifecycle_manager.shutdown_all()

        assert len(results) == 3
        assert all(results.values())
        assert all(r.shutdown_called for r in mock_resources.values())

    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, lifecycle_manager):
        """Завершение работы неинициализированного ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        results = await lifecycle_manager.shutdown_all()

        # Ресурс не был инициализирован, shutdown не вызывается
        # shutdown_all возвращает пустой dict если ничего не было инициализировано
        assert results == {}
        assert resource.shutdown_called is False

    @pytest.mark.asyncio
    async def test_shutdown_order_with_dependencies(self, lifecycle_manager):
        """Проверка порядка shutdown (обратный инициализации)."""
        shutdown_order = []

        class TrackedResource(MockResource):
            async def shutdown(self) -> None:
                shutdown_order.append(self.name)
                await super().shutdown()

        db_resource = TrackedResource("database")
        llm_resource = TrackedResource("llm")

        await lifecycle_manager.register_resource(
            "database", db_resource, ResourceType.DATABASE
        )
        await lifecycle_manager.register_resource(
            "llm", llm_resource, ResourceType.LLM, dependencies=["database"]
        )

        await lifecycle_manager.initialize_all()
        await lifecycle_manager.shutdown_all()

        # LLM должен завершиться раньше DATABASE (обратный порядок)
        assert shutdown_order == ["llm", "database"]


class TestHealthCheck:
    """Тесты проверки здоровья."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, lifecycle_manager):
        """Проверка здорового ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        await lifecycle_manager.initialize_all()

        results = await lifecycle_manager.health_check_all()

        assert "test_resource" in results
        assert results["test_resource"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_failed(self, lifecycle_manager):
        """Проверка ресурса с ошибкой health check."""
        resource = MockResource("test_resource", fail_health_check=True)

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )

        results = await lifecycle_manager.health_check_all()

        assert results["test_resource"]["status"] == "error"
        assert "error" in results["test_resource"]

    @pytest.mark.asyncio
    async def test_health_check_single_resource(self, lifecycle_manager):
        """Проверка здоровья одного ресурса."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        await lifecycle_manager.initialize_all()

        result = await lifecycle_manager.health_check_resource("test_resource")

        assert result is not None
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_resource(self, lifecycle_manager):
        """Проверка здоровья несуществующего ресурса."""
        result = await lifecycle_manager.health_check_resource("nonexistent")
        assert result is None


class TestResourceQueries:
    """Тесты получения ресурсов."""

    @pytest.mark.asyncio
    async def test_get_resource(self, lifecycle_manager):
        """Получение ресурса по имени."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )

        result = lifecycle_manager.get_resource("test_resource")
        assert result is resource

        result_none = lifecycle_manager.get_resource("nonexistent")
        assert result_none is None

    @pytest.mark.asyncio
    async def test_get_resources_by_type(self, lifecycle_manager):
        """Получение ресурсов по типу."""
        llm1 = MockResource("llm1")
        llm2 = MockResource("llm2")
        db = MockResource("db")

        await lifecycle_manager.register_resource("llm1", llm1, ResourceType.LLM)
        await lifecycle_manager.register_resource("llm2", llm2, ResourceType.LLM)
        await lifecycle_manager.register_resource("db", db, ResourceType.DATABASE)

        llm_resources = lifecycle_manager.get_resources_by_type(ResourceType.LLM)

        assert len(llm_resources) == 2
        assert llm1 in llm_resources
        assert llm2 in llm_resources
        assert db not in llm_resources


class TestLifecycleStats:
    """Тесты статистики lifecycle."""

    @pytest.mark.asyncio
    async def test_get_stats(self, lifecycle_manager, mock_resources):
        """Получение статистики."""
        for name, resource in mock_resources.items():
            resource_type = getattr(ResourceType, name.upper() if name != "storage" else "STORAGE")
            await lifecycle_manager.register_resource(name, resource, resource_type)

        await lifecycle_manager.initialize_all()

        stats = lifecycle_manager.get_stats()

        assert stats["total_resources"] == 3
        assert stats["initialized"] is True
        assert "initialized" in stats["by_status"]

    @pytest.mark.asyncio
    async def test_get_all_info(self, lifecycle_manager):
        """Получение информации обо всех ресурсах."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )

        info = lifecycle_manager.get_all_info()

        assert "test_resource" in info
        assert info["test_resource"]["name"] == "test_resource"
        assert info["test_resource"]["resource_type"] == "llm"

    @pytest.mark.asyncio
    async def test_initialized_count_property(self, lifecycle_manager):
        """Проверка свойства initialized_count."""
        resource = MockResource("test_resource")

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )

        assert lifecycle_manager.initialized_count == 0

        await lifecycle_manager.initialize_all()

        assert lifecycle_manager.initialized_count == 1

    @pytest.mark.asyncio
    async def test_is_initialized_property(self, lifecycle_manager):
        """Проверка свойства is_initialized."""
        resource = MockResource("test_resource")

        assert lifecycle_manager.is_initialized is False

        await lifecycle_manager.register_resource(
            "test_resource", resource, ResourceType.LLM
        )
        await lifecycle_manager.initialize_all()

        assert lifecycle_manager.is_initialized is True


class TestTopologicalSort:
    """Тесты топологической сортировки."""

    def test_topological_sort_simple(self, lifecycle_manager):
        """Простая топологическая сортировка."""
        graph = {
            "a": set(),
            "b": {"a"},
            "c": {"a", "b"},
        }
        order = lifecycle_manager._topological_sort(graph)
        
        assert order is not None
        # a должен быть раньше b, b раньше c
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_no_dependencies(self, lifecycle_manager):
        """Сортировка без зависимостей."""
        graph = {
            "a": set(),
            "b": set(),
            "c": set(),
        }
        order = lifecycle_manager._topological_sort(graph)
        
        assert order is not None
        assert len(order) == 3

    def test_topological_sort_circular(self, lifecycle_manager):
        """Сортировка с циклической зависимостью."""
        graph = {
            "a": {"b"},
            "b": {"a"},
        }
        order = lifecycle_manager._topological_sort(graph)
        
        assert order is None  # Цикл обнаружен
