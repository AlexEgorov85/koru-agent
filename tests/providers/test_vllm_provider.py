"""
Тесты для VLLMProvider.
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, call
import time

from providers.vllm_provider import VLLMProvider, VLlamaModelConfig
from providers.base_llm import LLMRequest, LLMResponse, LLMHealthStatus


@pytest.mark.asyncio
async def test_vllm_provider_initialization(mock_llm_config, mock_vllm_engine):
    """Тест инициализации VLLMProvider."""
    provider = VLLMProvider("test-model", mock_llm_config)
    
    assert provider.model_name == "test-model"
    assert provider.config == mock_llm_config
    assert isinstance(provider.engine_config, VLlamaModelConfig)
    
    # Мокаем загрузку движка
    with patch.object(provider, '_load_vllm_engine', return_value=mock_vllm_engine):
        success = await provider.initialize()
        
        assert success is True
        assert provider.is_initialized is True
        assert provider.health_status == LLMHealthStatus.HEALTHY
        assert provider.engine is mock_vllm_engine


@pytest.mark.asyncio
async def test_vllm_provider_shutdown(vllm_provider, mock_vllm_engine):
    """Тест завершения работы VLLMProvider."""
    assert vllm_provider.is_initialized is True
    
    # Мокаем shutdown движка
    mock_vllm_engine.shutdown = MagicMock()
    
    await vllm_provider.shutdown()
    
    mock_vllm_engine.shutdown.assert_called_once()
    assert vllm_provider.is_initialized is False
    assert vllm_provider.engine is None


@pytest.mark.asyncio
async def test_vllm_provider_health_check(vllm_provider, mock_vllm_engine):
    """Тест проверки здоровья VLLMProvider."""
    # Мокаем генерацию для health check
    mock_output = MagicMock()
    mock_output.outputs = [MagicMock(text="healthy")]
    mock_output.outputs[0].finish_reason = "stop"
    mock_output.prompt_token_ids = [1, 2, 3]
    mock_output.outputs[0].token_ids = [4, 5, 6]
    
    async def mock_generate(*args, **kwargs):
        yield mock_output
    
    mock_vllm_engine.generate = mock_generate
    
    result = await vllm_provider.health_check()
    
    assert result["status"] == LLMHealthStatus.HEALTHY.value
    assert result["model"] == "test-model"
    assert "response_time" in result
    assert result["is_initialized"] is True
    assert result["request_count"] == vllm_provider.request_count
    assert result["error_count"] == vllm_provider.error_count


@pytest.mark.asyncio
async def test_vllm_provider_generate(vllm_provider, mock_vllm_engine):
    """Тест генерации текста."""
    # Мокаем ответ от vLLM
    mock_output = MagicMock()
    mock_output.outputs = [MagicMock(text="Generated response")]
    mock_output.outputs[0].finish_reason = "stop"
    mock_output.prompt_token_ids = [1, 2, 3]
    mock_output.outputs[0].token_ids = [4, 5, 6]
    
    async def mock_generate(*args, **kwargs):
        yield mock_output
    
    mock_vllm_engine.generate = mock_generate
    
    request = LLMRequest(
        prompt="Test prompt",
        system_prompt="You are an AI assistant",
        temperature=0.7,
        max_tokens=100,
        top_p=0.95
    )
    
    response = await vllm_provider.generate(request)
    
    assert isinstance(response, LLMResponse)
    assert response.content == "Generated response"
    assert response.model == "test-model"
    assert response.tokens_used == 3  # len([4, 5, 6])
    assert response.generation_time > 0
    assert response.finish_reason == "stop"
    assert "request_id" in response.metadata
    assert response.metadata["prompt_tokens"] == 3
    assert response.metadata["completion_tokens"] == 3
    assert response.metadata["total_tokens"] == 6

    # Проверяем, что метрики обновлены
    assert vllm_provider.request_count == 1
    assert vllm_provider.error_count == 0
    assert vllm_provider.avg_response_time > 0


@pytest.mark.asyncio
async def test_vllm_provider_generate_structured(vllm_provider, mock_vllm_engine):
    """Тест генерации структурированных данных."""
    # Мокаем генерацию для JSON Mode
    mock_output = MagicMock()
    mock_output.outputs = [MagicMock(text='{"result": "structured_data"}')]
    mock_output.outputs[0].finish_reason = "stop"
    mock_output.prompt_token_ids = [1, 2, 3]
    mock_output.outputs[0].token_ids = [4, 5, 6]
    
    async def mock_generate(*args, **kwargs):
        yield mock_output
    
    mock_vllm_engine.generate = mock_generate
    
    schema = {
        "type": "object",
        "properties": {
            "result": {"type": "string"}
        },
        "required": ["result"]
    }
    
    result = await vllm_provider.generate_structured(
        prompt="Test structured prompt",
        output_schema=schema,
        system_prompt="You are a JSON generator"
    )
    
    assert result == {"result": "structured_data"}
    
    # Проверяем вызов с правильными параметрами
    mock_vllm_engine.generate.assert_called_once()
    # Проверяем, что использовался JSON Mode
    assert "response_format" in mock_vllm_engine.generate.call_args[1].get("metadata", {})


@pytest.mark.asyncio
async def test_vllm_provider_generate_error_handling(vllm_provider, mock_vllm_engine):
    """Тест обработки ошибок при генерации."""
    # Мокаем ошибку при генерации
    async def mock_generate_with_error(*args, **kwargs):
        raise ValueError("Test error")
    
    mock_vllm_engine.generate = mock_generate_with_error
    
    request = LLMRequest(
        prompt="Test prompt",
        temperature=0.7,
        max_tokens=100
    )
    
    with pytest.raises(Exception) as exc_info:
        await vllm_provider.generate(request)
    
    assert "Test error" in str(exc_info.value)
    assert vllm_provider.error_count == 1
    assert vllm_provider.health_status == LLMHealthStatus.UNKNOWN  # Одна ошибка не должна менять статус


@pytest.mark.asyncio
async def test_vllm_provider_reinitialization(vllm_provider, mock_vllm_engine):
    """Тест повторной инициализации после ошибки."""
    # Имитируем ошибку инициализации
    with patch.object(vllm_provider, '_load_vllm_engine', side_effect=Exception("Initialization error")):
        success = await vllm_provider.initialize()
        assert success is False
        assert vllm_provider.health_status == LLMHealthStatus.UNHEALTHY
    
    # Пытаемся повторно инициализировать
    with patch.object(vllm_provider, '_load_vllm_engine', return_value=mock_vllm_engine):
        success = await vllm_provider.initialize()
        assert success is True
        assert vllm_provider.health_status == LLMHealthStatus.HEALTHY