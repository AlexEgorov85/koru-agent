"""
Фикстуры для интеграционных тестов инфраструктуры.

Создаёт инфраструктурный контекст ОДИН раз на сессию тестов.
Автоматически завершает работу после всех тестов.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch

from core.config.registry_loader import RegistryLoader as ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext


@pytest.fixture(scope="session")
async def infrastructure_context():
    """
    Фикстура: поднимает инфраструктурный контекст ОДИН раз на сессию тестов.
    Автоматически завершает работу после всех тестов.
    """
    # Пропускаем, если нет флага (для локальной разработки без ресурсов)
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Пропущено: нет флага RUN_INTEGRATION_TESTS")
    
    # Поднимаем инфраструктуру
    config_loader = ConfigLoader()
    config = config_loader.load()  # test.yaml с лёгкими настройками
    
    infra = InfrastructureContext(config)
    
    try:
        # Для интеграционных тестов нужно использовать реальные провайдеры
        # но с легкими настройками
        await infra.initialize()
        yield infra
    finally:
        # Гарантированное завершение работы
        await infra.shutdown()


@pytest.fixture(scope="session")
def light_config():
    """
    Фикстура: возвращает легковесную конфигурацию для тестов.
    """
    # Создаем минимальную конфигурацию для тестов
    from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
    
    config = SystemConfig(
        llm_providers={
            "test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="test-model",
                enabled=True,
                parameters={
                    "model_path": "models/test-model.gguf",  # будет замокано
                    "n_ctx": 512,  # маленький контекст для быстрого тестирования
                    "n_threads": 1,
                    "verbose": False
                }
            )
        },
        db_providers={
            "test_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"  # in-memory база для тестов
                }
            )
        }
    )
    
    return config


@pytest.fixture
async def mock_infrastructure_context(light_config):
    """
    Фикстура: создаёт инфраструктурный контекст с моками для избежания 
    необходимости реальных ресурсов при тестировании архитектурных гарантий.
    """
    infra = InfrastructureContext(light_config)
    
    # Мокаем провайдеры чтобы не требовать реальных ресурсов
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        # Создаем мок-провайдеры
        mock_llm_provider = AsyncMock()
        mock_llm_provider.initialize = AsyncMock()
        mock_llm_provider.shutdown = AsyncMock()
        mock_llm_factory.return_value = mock_llm_provider
        
        mock_db_provider = AsyncMock()
        mock_db_provider.initialize = AsyncMock()
        mock_db_provider.shutdown = AsyncMock()
        mock_db_factory.return_value = mock_db_provider
        
        await infra.initialize()
        yield infra