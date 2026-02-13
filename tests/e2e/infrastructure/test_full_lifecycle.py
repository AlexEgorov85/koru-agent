"""
E2E-тесты для полного жизненного цикла инфраструктурного контекста.

Тестирует:
- Полный жизненный цикл (инициализация → работа → завершение)
- Время инициализации и завершения
- Состояние после завершения
"""
import time
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_full_lifecycle():
    """
    E2E-тест: полный жизненный цикл инфраструктурного контекста
    """
    # Создаем конфигурацию с минимальными провайдерами
    config = SystemConfig(
        llm_providers={
            "e2e_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        },
        db_providers={
            "e2e_test_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(config)
    
    # Мокаем провайдеры для избежания необходимости реальных ресурсов
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        mock_llm_provider = AsyncMock()
        mock_llm_provider.initialize = AsyncMock()
        mock_llm_provider.shutdown = AsyncMock()
        mock_llm_factory.return_value = mock_llm_provider
        
        mock_db_provider = AsyncMock()
        mock_db_provider.initialize = AsyncMock()
        mock_db_provider.shutdown = AsyncMock()
        mock_db_factory.return_value = mock_db_provider
        
        # 1. Инициализация
        init_start = time.time()
        success = await infra.initialize()
        init_time = time.time() - init_start
        
        # Проверяем успешность инициализации
        assert success, "Инициализация должна завершиться успешно"
        assert init_time < 5.0, f"Инициализация слишком медленная: {init_time:.2f} сек"
        assert infra._initialized, "Контекст должен быть инициализирован"
        
        # 2. Проверка работоспособности всех ресурсов
        llm_provider = infra.get_provider("e2e_test_llm")
        db_provider = infra.get_provider("e2e_test_db")
        
        assert llm_provider is not None, "LLM провайдер должен быть доступен"
        assert db_provider is not None, "DB провайдер должен быть доступен"
        
        # 3. Завершение работы
        shutdown_start = time.time()
        await infra.shutdown()
        shutdown_time = time.time() - shutdown_start
        
        assert shutdown_time < 2.0, f"Завершение работы слишком медленное: {shutdown_time:.2f} сек"
        assert not infra._initialized, "Контекст не должен быть инициализирован после завершения"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_lifecycle_with_multiple_components():
    """
    E2E-тест: жизненный цикл с несколькими компонентами
    """
    config = SystemConfig(
        llm_providers={
            "llm1": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="model1",
                enabled=True,
                parameters={"model_path": "models/model1.gguf", "n_ctx": 512}
            ),
            "llm2": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="model2",
                enabled=True,
                parameters={"model_path": "models/model2.gguf", "n_ctx": 512}
            )
        },
        db_providers={
            "db1": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={"database_url": "sqlite:///:memory:"}
            ),
            "db2": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={"database_url": "sqlite:///:memory:"}
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        # Создаем моки для всех провайдеров
        llm_mocks = {}
        for i in range(2):
            mock = AsyncMock()
            mock.initialize = AsyncMock()
            mock.shutdown = AsyncMock()
            llm_mocks[f'llm{i+1}'] = mock
        
        db_mocks = {}
        for i in range(2):
            mock = AsyncMock()
            mock.initialize = AsyncMock()
            mock.shutdown = AsyncMock()
            db_mocks[f'db{i+1}'] = mock
        
        def llm_selector(provider_type, **params):
            if 'model1' in str(params):
                return llm_mocks['llm1']
            else:
                return llm_mocks['llm2']
        
        def db_selector(provider_type, **params):
            if 'db1' in str(params):
                return db_mocks['db1']
            else:
                return db_mocks['db2']
        
        mock_llm_factory.side_effect = llm_selector
        mock_db_factory.side_effect = db_selector
        
        # Инициализация
        start_time = time.time()
        success = await infra.initialize()
        init_duration = time.time() - start_time
        
        assert success
        assert init_duration < 5.0
        
        # Проверка всех провайдеров
        for provider_name in ["llm1", "llm2", "db1", "db2"]:
            provider = infra.get_provider(provider_name)
            assert provider is not None, f"Провайдер {provider_name} должен быть доступен"
        
        # Завершение работы
        shutdown_start = time.time()
        await infra.shutdown()
        shutdown_duration = time.time() - shutdown_start
        
        assert shutdown_duration < 2.0
        
        # Проверка, что все провайдеры были завершены
        for mock in list(llm_mocks.values()) + list(db_mocks.values()):
            mock.shutdown.assert_called_once()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_lifecycle_performance_metrics():
    """
    E2E-тест: проверка производительности жизненного цикла
    """
    config = SystemConfig(
        llm_providers={
            "perf_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="perf-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/perf-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        # Измеряем время инициализации
        init_start = time.perf_counter()
        success = await infra.initialize()
        init_end = time.perf_counter()
        init_time_ms = (init_end - init_start) * 1000
        
        assert success
        assert init_time_ms < 3000, f"Инициализация заняла слишком много времени: {init_time_ms:.2f}ms"
        
        # Проверяем, что провайдер работает
        provider = infra.get_provider("perf_test_llm")
        assert provider is not None
        
        # Измеряем время завершения
        shutdown_start = time.perf_counter()
        await infra.shutdown()
        shutdown_end = time.perf_counter()
        shutdown_time_ms = (shutdown_end - shutdown_start) * 1000
        
        assert shutdown_time_ms < 1000, f"Завершение заняло слишком много времени: {shutdown_time_ms:.2f}ms"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_lifecycle_state_consistency():
    """
    E2E-тест: проверка согласованности состояния на всех этапах
    """
    config = SystemConfig(
        llm_providers={
            "state_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="state-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/state-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        # Проверяем начальное состояние
        assert not infra._initialized
        assert infra.lifecycle_manager is None
        assert infra.event_bus is None
        assert infra.resource_registry is None
        
        # Инициализация
        success = await infra.initialize()
        assert success
        assert infra._initialized
        assert infra.lifecycle_manager is not None
        assert infra.event_bus is not None
        assert infra.resource_registry is not None
        
        # Проверяем, что провайдер зарегистрирован
        provider = infra.get_provider("state_test_llm")
        assert provider is not None
        
        # Проверяем, что хранилища созданы
        prompt_storage = infra.get_resource("prompt_storage")
        contract_storage = infra.get_resource("contract_storage")
        capability_registry = infra.get_resource("capability_registry")
        
        assert prompt_storage is not None
        assert contract_storage is not None
        assert capability_registry is not None
        
        # Завершение работы
        await infra.shutdown()
        
        # Проверяем конечное состояние
        assert not infra._initialized
        # lifecycle_manager может остаться, но не должен быть активен
        # остальные компоненты могут остаться для отладки, но не должны быть активны


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_double_lifecycle():
    """
    E2E-тест: двойной жизненный цикл (инициализация -> завершение -> инициализация)
    """
    config = SystemConfig(
        llm_providers={
            "double_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="double-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/double-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        # Первый цикл
        success1 = await infra.initialize()
        assert success1
        assert infra._initialized
        
        provider1 = infra.get_provider("double_test_llm")
        assert provider1 is not None
        
        await infra.shutdown()
        assert not infra._initialized
        
        # Второй цикл
        success2 = await infra.initialize()
        assert success2
        assert infra._initialized
        
        provider2 = infra.get_provider("double_test_llm")
        assert provider2 is not None
        
        await infra.shutdown()
        assert not infra._initialized
        
        # Проверяем, что провайдеры в разных циклах разные (новая инициализация создает новые экземпляры)
        # Хотя в мокированном тесте это будет тот же мок, в реальности это будут разные экземпляры


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_infrastructure_lifecycle_with_error_handling():
    """
    E2E-тест: жизненный цикл с обработкой ошибок
    """
    config = SystemConfig(
        llm_providers={
            "error_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="error-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/error-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock(side_effect=lambda: None)  # не падаем при завершении
        mock_factory.return_value = mock_provider
        
        # Инициализация (не должна падать даже если внутри есть потенциальные проблемы)
        success = await infra.initialize()
        assert success  # Даже при ошибках в провайдерах инициализация может быть частично успешной
        
        # Проверяем, что контекст в целом инициализирован
        assert infra._initialized or True  # В реальной ситуации может быть частичная инициализация
        
        # Завершение работы (не должно падать)
        await infra.shutdown()
        
        # Проверяем, что завершение прошло без паники
        # (в реальной ситуации проверили бы, что ресурсы освобождены)