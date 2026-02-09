"""
Тесты для ProviderFactory.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.infrastructure.providers.factory import ProviderFactory
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from core.infrastructure.providers.database.postgres_provider import PostgreSQLProvider
from models.db_types import DBConnectionConfig


@pytest.mark.parametrize("provider_type, expected_class", [
    ("llama_cpp", LlamaCppProvider),
])
def test_create_llm_provider(provider_type, expected_class):
    """Тест создания LLM провайдера."""
    # Мокируем класс в месте импорта в фабрике
    with patch("core.infrastructure.providers.factory.LlamaCppProvider") as mock_provider_class:
        mock_instance = MagicMock(spec=BaseLLMProvider)
        mock_provider_class.return_value = mock_instance

        # Для LlamaCppProvider передаем конфигурацию с model_path
        config = {"model_path": "test-model.gguf", "n_ctx": 2048}
        provider = ProviderFactory.create_llm_provider(
            provider_type=provider_type,
            model_name="test-model",
            config=config
        )

        # Проверяем, что вызов был с правильными аргументами
        mock_provider_class.assert_called_once_with(model_name="test-model", config=config)
        assert provider is mock_instance


def test_create_llm_provider_unsupported_type():
    """Тест создания LLM провайдера с неподдерживаемым типом."""
    with pytest.raises(ValueError) as exc_info:
        ProviderFactory.create_llm_provider(
            provider_type="unsupported",
            model_name="test-model"
        )
    
    assert "Unsupported LLM provider type: unsupported" in str(exc_info.value)


@pytest.mark.parametrize("provider_type, expected_class", [
    ("postgres", PostgreSQLProvider),
])
def test_create_db_provider(provider_type, expected_class, mock_db_config):
    """Тест создания DB провайдера."""
    # Мокируем класс в месте импорта в фабрике
    with patch("core.infrastructure.providers.factory.PostgreSQLProvider") as mock_provider:
        mock_instance = MagicMock(spec=BaseDBProvider)
        mock_provider.return_value = mock_instance

        config_obj = DBConnectionConfig(**mock_db_config)
        provider = ProviderFactory.create_db_provider(
            provider_type=provider_type,
            config=config_obj
        )

        mock_provider.assert_called_once()
        # Проверяем, что конфиг был передан как DBConnectionConfig
        args, kwargs = mock_provider.call_args
        if args:
            assert isinstance(args[0], DBConnectionConfig)
        else:
            assert isinstance(kwargs.get('config'), DBConnectionConfig)
        assert provider is mock_instance


def test_create_db_provider_unsupported_type():
    """Тест создания DB провайдера с неподдерживаемым типом."""
    with pytest.raises(ValueError) as exc_info:
        ProviderFactory.create_db_provider(
            provider_type="unsupported",
            config={"host": "localhost", "port": 5432}
        )
    
    assert "Unsupported DB provider type: unsupported" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [
    LlamaCppProvider,
    PostgreSQLProvider,
])
async def test_initialize_provider(provider_class):
    """Тест инициализации провайдера."""
    mock_provider = MagicMock(spec=provider_class)
    mock_provider.initialize = AsyncMock(return_value=True)

    success = await ProviderFactory.initialize_provider(mock_provider)

    mock_provider.initialize.assert_called_once()
    assert success is True


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [
    LlamaCppProvider,
    PostgreSQLProvider,
])
async def test_initialize_provider_failure(provider_class):
    """Тест инициализации провайдера с ошибкой."""
    mock_provider = MagicMock(spec=provider_class)
    mock_provider.initialize = AsyncMock(side_effect=Exception("Test error"))

    success = await ProviderFactory.initialize_provider(mock_provider)

    mock_provider.initialize.assert_called_once()
    assert success is False


@pytest.mark.asyncio
async def test_create_and_initialize_llm(mock_llm_config):
    """Тест создания и инициализации LLM провайдера."""
    # Мокируем как создание провайдера, так и его инициализацию
    with patch("core.infrastructure.providers.factory.ProviderFactory.create_llm_provider") as mock_create:
        with patch("core.infrastructure.providers.factory.ProviderFactory.initialize_provider") as mock_init:
            mock_provider = AsyncMock()
            mock_create.return_value = mock_provider
            mock_init.return_value = True

            provider = await ProviderFactory.create_and_initialize_llm(
                provider_type="llama_cpp",
                model_name="test-model",
                config=mock_llm_config
            )

            mock_create.assert_called_once_with("llama_cpp", "test-model", mock_llm_config)
            mock_init.assert_called_once_with(mock_provider)
            assert provider is mock_provider


@pytest.mark.asyncio
async def test_create_and_initialize_llm_failure(mock_llm_config):
    """Тест создания и инициализации LLM провайдера с ошибкой."""
    # Мокируем как создание провайдера, так и его инициализацию
    with patch("core.infrastructure.providers.factory.ProviderFactory.create_llm_provider") as mock_create:
        with patch("core.infrastructure.providers.factory.ProviderFactory.initialize_provider") as mock_init:
            mock_provider = AsyncMock()
            mock_create.return_value = mock_provider
            mock_init.return_value = False  # Симулируем неудачную инициализацию

            with pytest.raises(RuntimeError) as exc_info:
                await ProviderFactory.create_and_initialize_llm(
                    provider_type="llama_cpp",
                    model_name="test-model",
                    config=mock_llm_config
                )

            mock_create.assert_called_once_with("llama_cpp", "test-model", mock_llm_config)
            mock_init.assert_called_once_with(mock_provider)
            assert "Не удалось инициализировать LLM провайдер типа llama_cpp" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_and_initialize_db(db_connection_config):
    """Тест создания и инициализации DB провайдера."""
    # Мокируем как создание провайдера, так и его инициализацию
    with patch("core.infrastructure.providers.factory.ProviderFactory.create_db_provider") as mock_create:
        with patch("core.infrastructure.providers.factory.ProviderFactory.initialize_provider") as mock_init:
            mock_provider = AsyncMock()
            mock_create.return_value = mock_provider
            mock_init.return_value = True

            provider = await ProviderFactory.create_and_initialize_db(
                provider_type="postgres",
                config=db_connection_config
            )

            mock_create.assert_called_once_with("postgres", db_connection_config)
            mock_init.assert_called_once_with(mock_provider)
            assert provider is mock_provider


@pytest.mark.asyncio
async def test_create_and_initialize_db_failure(db_connection_config):
    """Тест создания и инициализации DB провайдера с ошибкой."""
    # Мокируем как создание провайдера, так и его инициализацию
    with patch("core.infrastructure.providers.factory.ProviderFactory.create_db_provider") as mock_create:
        with patch("core.infrastructure.providers.factory.ProviderFactory.initialize_provider") as mock_init:
            mock_provider = AsyncMock()
            mock_create.return_value = mock_provider
            mock_init.return_value = False  # Симулируем неудачную инициализацию

            with pytest.raises(RuntimeError) as exc_info:
                await ProviderFactory.create_and_initialize_db(
                    provider_type="postgres",
                    config=db_connection_config
                )

            mock_create.assert_called_once_with("postgres", db_connection_config)
            mock_init.assert_called_once_with(mock_provider)
            assert "Не удалось инициализировать DB провайдер типа postgres" in str(exc_info.value)