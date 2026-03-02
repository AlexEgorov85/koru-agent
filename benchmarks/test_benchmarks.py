"""
Performance benchmarks для Agent_v5.

Запуск:
    pytest benchmarks/ -v --benchmark-only
    pytest benchmarks/ -v --benchmark-compare  # сравнение с предыдущим запуском

Сравнение версий:
    pytest benchmarks/ -v --benchmark-compare=0001.json --benchmark-save=0002.json
"""
import pytest
import asyncio
from pathlib import Path

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def system_config():
    """Базовая системная конфигурация для бенчмарков."""
    return SystemConfig(
        debug=False,
        log_level="ERROR",
        data_dir="./data"
    )


@pytest.fixture
async def infrastructure_context(system_config):
    """InfrastructureContext для бенчмарков."""
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.fixture
async def application_context(infrastructure_context):
    """ApplicationContext для бенчмарков."""
    app_config = AppConfig.from_discovery(profile='prod', data_dir='data')
    app_context = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=app_config,
        profile='prod'
    )
    await app_context.initialize()
    yield app_context


# ============================================================================
# BENCHMARKS: Инициализация
# ============================================================================

class TestInitializationBenchmarks:
    """Бенчмарки инициализации компонентов."""

    def test_system_config_creation(self, benchmark):
        """Бенчмарк: Создание SystemConfig."""
        def create_config():
            return SystemConfig(
                debug=False,
                log_level="ERROR",
                data_dir="./data"
            )
        
        result = benchmark(create_config)
        assert result is not None
        # Цель: < 1 мс

    def test_infrastructure_context_init(self, benchmark, system_config):
        """Бенчмарк: Инициализация InfrastructureContext."""
        async def init_infra():
            infra = InfrastructureContext(system_config)
            await infra.initialize()
            await infra.shutdown()
            return infra
        
        result = benchmark(asyncio.run, init_infra)
        assert result is not None
        # Цель: < 100 мс

    def test_app_config_from_discovery(self, benchmark):
        """Бенчмарк: Загрузка AppConfig через discovery."""
        def load_config():
            return AppConfig.from_discovery(profile='prod', data_dir='data')

        result = benchmark(load_config)
        assert result is not None
        # Цель: < 50 мс

    def test_application_context_init(self, benchmark, infrastructure_context):
        """Бенчмарк: Инициализация ApplicationContext."""
        async def init_app():
            app_config = AppConfig.from_discovery(profile='prod', data_dir='data')
            app_context = ApplicationContext(
                infrastructure_context=infrastructure_context,
                config=app_config,
                profile='prod'
            )
            await app_context.initialize()
            return app_context

        result = benchmark(asyncio.run, init_app)
        assert result is not None
        # Цель: < 500 мс


# ============================================================================
# BENCHMARKS: Загрузка компонентов
# ============================================================================

class TestComponentLoadingBenchmarks:
    """Бенчмарки загрузки компонентов."""

    def test_load_manifests(self, benchmark, application_context):
        """Бенчмарк: Загрузка манифестов."""
        def load_manifests():
            return application_context.data_repository._manifest_cache
        
        result = benchmark(load_manifests)
        assert len(result) > 0
        # Цель: < 10 мс

    def test_get_skill(self, benchmark, application_context):
        """Бенчмарк: Получение навыка по имени."""
        def get_skill():
            return application_context.get_skill("planning")
        
        result = benchmark(get_skill)
        assert result is not None
        # Цель: < 1 мс

    def test_get_service(self, benchmark, application_context):
        """Бенчмарк: Получение сервиса по имени."""
        def get_service():
            return application_context.get_service("prompt_service")
        
        result = benchmark(get_service)
        assert result is not None
        # Цель: < 1 мс

    def test_get_tool(self, benchmark, application_context):
        """Бенчмарк: Получение инструмента по имени."""
        def get_tool():
            return application_context.get_tool("file_tool")
        
        result = benchmark(get_tool)
        assert result is not None
        # Цель: < 1 мс


# ============================================================================
# BENCHMARKS: Промпты и контракты
# ============================================================================

class TestPromptContractBenchmarks:
    """Бенчмарки работы с промптами и контрактами."""

    def test_get_prompt(self, benchmark, application_context):
        """Бенчмарк: Получение промпта."""
        def get_prompt():
            return application_context.get_prompt(
                "planning.create_plan",
                "v1.0.0"
            )
        
        result = benchmark(get_prompt)
        assert result is not None
        # Цель: < 5 мс

    def test_get_contract(self, benchmark, application_context):
        """Бенчмарк: Получение контракта."""
        def get_contract():
            return application_context.data_repository.get_contract(
                "planning.create_plan",
                "v1.0.0",
                "input"
            )
        
        result = benchmark(get_contract)
        assert result is not None
        # Цель: < 5 мс

    def test_render_prompt(self, benchmark, application_context):
        """Бенчмарк: Рендеринг промпта."""
        def render_prompt():
            prompt = application_context.get_prompt(
                "planning.create_plan",
                "v1.0.0"
            )
            return prompt.render(
                goal="Test goal",
                capabilities_list=["cap1", "cap2"]
            )
        
        result = benchmark(render_prompt)
        assert result is not None
        # Цель: < 10 мс


# ============================================================================
# BENCHMARKS: Память
# ============================================================================

class TestMemoryBenchmarks:
    """Бенчмарки использования памяти."""

    def test_context_memory_usage(self, benchmark):
        """Бенчмарк: Использование памяти контекстами."""
        import tracemalloc
        
        async def measure_memory():
            tracemalloc.start()
            
            config = SystemConfig(data_dir="./data")
            infra = InfrastructureContext(config)
            await infra.initialize()

            app_config = AppConfig.from_discovery(profile='prod', data_dir='data')
            app_context = ApplicationContext(
                infrastructure_context=infra,
                config=app_config,
                profile='prod'
            )
            await app_context.initialize()

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            await infra.shutdown()

            return peak
        
        peak_memory = benchmark(asyncio.run, measure_memory)
        # Цель: < 100 МБ на контекст
        assert peak_memory < 100 * 1024 * 1024  # 100 MB


# ============================================================================
# BENCHMARKS: Параллельное выполнение
# ============================================================================

class TestParallelBenchmarks:
    """Бенчмарки параллельного выполнения."""

    @pytest.mark.parametrize("agent_count", [1, 5, 10])
    def test_multiple_agents_init(self, benchmark, system_config, agent_count):
        """Бенчмарк: Инициализация нескольких агентов параллельно."""
        async def init_agents():
            contexts = []
            for i in range(agent_count):
                infra = InfrastructureContext(system_config)
                await infra.initialize()

                app_config = AppConfig.from_discovery(profile='prod', data_dir='data')
                app_context = ApplicationContext(
                    infrastructure_context=infra,
                    config=app_config,
                    profile='prod'
                )
                await app_context.initialize()

                contexts.append((infra, app_context))

            # Cleanup
            for infra, _ in contexts:
                await infra.shutdown()
            
            return len(contexts)
        
        result = benchmark(asyncio.run, init_agents)
        assert result == agent_count
        # Цель: < 1 сек для 10 агентов
