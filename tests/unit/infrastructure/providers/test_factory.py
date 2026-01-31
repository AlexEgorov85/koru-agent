"""
Тесты для ProviderFactory.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.providers.database.base_db import BaseDBProvider, DBConnectionConfig
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from core.infrastructure.providers.database.postgres_provider import PostgreSQLProvider
from core.system_context.factory import ProviderFactory


def test_create_llm_provider():
    """Тест создания LLM провайдера."""
    # Тестируем только llama_cpp, так как VLLMProvider не реализован
    with patch("core.infrastructure.providers.llm.llama_cpp_provider.LlamaCppProvider") as mock_provider:
        mock_instance = MagicMock(spec=BaseLLMProvider)
        mock_provider.return_value = mock_instance
        
        provider = ProviderFactory.create_llm_provider(
            provider_type="llama_cpp",
            model_name="test-model",
            config={"param": "value"}
        )
        
        mock_provider.assert_called_once_with("test-model", {"param": "value"})
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
    with patch(f"core.infrastructure.providers.database.{provider_type}_provider.{expected_class.__name__}") as mock_provider:
        mock_instance = MagicMock(spec=BaseDBProvider)
        mock_provider.return_value = mock_instance
        
        provider = ProviderFactory.create_db_provider(
            provider_type=provider_type,
            config=mock_db_config
        )
        
        mock_provider.assert_called_once()
        # Проверяем, что конфиг был преобразован в DBConnectionConfig
        assert isinstance(mock_provider.call_args[0][0], DBConnectionConfig)
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
@pytest.mark.asyncio
async def test_initialize_provider():
    """Тест инициализации провайдера."""
    mock_provider = MagicMock(spec=LlamaCppProvider)
    mock_provider.initialize = AsyncMock(return_value=True)
    
    success = await ProviderFactory.initialize_provider(mock_provider)
    
    mock_provider.initialize.assert_called_once()
    assert success is True


@pytest.mark.asyncio
async def test_initialize_provider_failure():
    """Тест инициализации провайдера с ошибкой."""
    mock_provider = MagicMock(spec=LlamaCppProvider)
    mock_provider.initialize = AsyncMock(side_effect=Exception("Test error"))
    
    success = await ProviderFactory.initialize_provider(mock_provider)
    
    mock_provider.initialize.assert_called_once()
    assert success is False


# Пропускаем тесты для VLLMProvider, так как он не реализован
# @pytest.mark.asyncio
# async def test_create_and_initialize_llm(mock_llm_config):
#     """Тест создания и инициализации LLM провайдера."""
#     with patch("core.infrastructure.providers.llm.vllm_provider.VLLMProvider") as mock_provider_class:
#         mock_provider = AsyncMock(spec=VLLMProvider)
#         mock_provider.initialize.return_value = True
#         mock_provider_class.return_value = mock_provider
#         
#         provider = await ProviderFactory.create_and_initialize_llm(
#             provider_type="vllm",
#             model_name="test-model",
#             config=mock_llm_config
#         )
#         
#         mock_provider_class.assert_called_once_with("test-model", mock_llm_config)
#         mock_provider.initialize.assert_called_once()
#         assert provider is mock_provider
# 
# 
# @pytest.mark.asyncio
# async def test_create_and_initialize_llm_failure(mock_llm_config):
#     """Тест создания и инициализации LLM провайдера с ошибкой."""
#     with patch("core.infrastructure.providers.llm.vllm_provider.VLLMProvider") as mock_provider_class:
#         mock_provider = AsyncMock(spec=VLLMProvider)
#         mock_provider.initialize.return_value = False
#         mock_provider_class.return_value = mock_provider
#         
#         with pytest.raises(RuntimeError) as exc_info:
#             await ProviderFactory.create_and_initialize_llm(
#                 provider_type="vllm",
#                 model_name="test-model",
#                 config=mock_llm_config
#             )
#             
#         assert "Failed to initialize LLM provider vllm" in str(exc_info.value)
#         mock_provider.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_create_and_initialize_db(db_connection_config):
    """Тест создания и инициализации DB провайдера."""
    with patch("core.infrastructure.providers.database.postgres_provider.PostgreSQLProvider") as mock_provider_class:
        mock_provider = AsyncMock(spec=PostgreSQLProvider)
        mock_provider.initialize.return_value = True
        mock_provider_class.return_value = mock_provider
        
        provider = await ProviderFactory.create_and_initialize_db(
            provider_type="postgres",
            config=db_connection_config
        )
        
        mock_provider_class.assert_called_once_with(db_connection_config)
        mock_provider.initialize.assert_called_once()
        assert provider is mock_provider


@pytest.mark.asyncio
async def test_create_and_initialize_db_failure(db_connection_config):
    """Тест создания и инициализации DB провайдера с ошибкой."""
    with patch("core.infrastructure.providers.database.postgres_provider.PostgreSQLProvider") as mock_provider_class:
        mock_provider = AsyncMock(spec=PostgreSQLProvider)
        mock_provider.initialize.return_value = False
        mock_provider_class.return_value = mock_provider
        
        with pytest.raises(RuntimeError) as exc_info:
            await ProviderFactory.create_and_initialize_db(
                provider_type="postgres",
                config=db_connection_config
            )
        
        assert "Failed to initialize DB provider postgres" in str(exc_info.value)
        mock_provider.initialize.assert_called_once()
