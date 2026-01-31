"""
Тесты для базового класса LLM-провайдеров.
"""
import pytest
import json
import time
from unittest.mock import MagicMock, AsyncMock, patch

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider, LLMRequest, LLMResponse, LLMHealthStatus
from models.capability import Capability


class MockLLMProvider(BaseLLMProvider):
    """Мок-реализация BaseLLMProvider для тестов."""
    
    async def initialize(self) -> bool:
        self.is_initialized = True
        return True
    
    async def shutdown(self) -> None:
        self.is_initialized = False
    
    async def health_check(self) -> dict:
        return {"status": self.health_status.value, "model": self.model_name}
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=f"Response to: {request.prompt}",
            model=self.model_name,
            tokens_used=10,
            generation_time=0.1,
            finish_reason="stop"
        )
    
    async def generate_structured(self, request: LLMRequest, output_schema: dict) -> LLMResponse:
        return LLMResponse(
            content={"result": "structured_data"},
            model=self.model_name,
            tokens_used=10,
            generation_time=0.1,
            finish_reason="stop"
        )


@pytest.fixture
def base_provider():
    """Фикстура с базовым LLM провайдером."""
    return MockLLMProvider("test-model", {"temperature": 0.7})


@pytest.mark.asyncio
async def test_base_provider_initialization(base_provider):
    """Тест инициализации базового провайдера."""
    assert base_provider.model_name == "test-model"
    assert base_provider.config["temperature"] == 0.7
    assert base_provider.is_initialized is False
    assert base_provider.health_status == LLMHealthStatus.UNKNOWN
    
    # Тестируем инициализацию
    await base_provider.initialize()
    assert base_provider.is_initialized is True
    assert base_provider.health_status == LLMHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_base_provider_shutdown(base_provider):
    """Тест завершения работы провайдера."""
    await base_provider.initialize()
    assert base_provider.is_initialized is True
    
    await base_provider.shutdown()
    assert base_provider.is_initialized is False


@pytest.mark.asyncio
async def test_base_provider_health_check(base_provider):
    """Тест проверки здоровья провайдера."""
    await base_provider.initialize()
    result = await base_provider.health_check()
    
    assert result["status"] == LLMHealthStatus.HEALTHY.value
    assert result["model"] == "test-model"


@pytest.mark.asyncio
async def test_base_provider_generate(base_provider):
    """Тест генерации текста."""
    await base_provider.initialize()
    
    request = LLMRequest(
        prompt="Test prompt",
        temperature=0.5,
        max_tokens=100
    )
    
    response = await base_provider.generate(request)
    
    assert response.content.startswith("Response to: Test prompt")
    assert response.model == "test-model"
    assert response.tokens_used == 10
    assert response.generation_time > 0
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_base_provider_generate_structured(base_provider):
    """Тест генерации структурированных данных."""
    await base_provider.initialize()
    
    schema = {
        "type": "object",
        "properties": {
            "result": {"type": "string"}
        },
        "required": ["result"]
    }
    
    request = LLMRequest(
        prompt="Test structured prompt",
        temperature=0.7,
        max_tokens=100
    )
    result = await base_provider.generate_structured(request, schema)
    
    assert isinstance(result, LLMResponse)
    assert result.content == {"result": "structured_data"}


def test_base_provider_get_model_info(base_provider):
    """Тест получения информации о модели."""
    info = base_provider.get_model_info()
    
    assert info["model_name"] == "test-model"
    assert info["provider_type"] == "MockLLMProvider"
    assert info["is_initialized"] is False
    assert info["health_status"] == LLMHealthStatus.UNKNOWN.value
    assert info["uptime_seconds"] > 0
    assert info["request_count"] == 0
    assert info["error_count"] == 0
    assert info["avg_response_time"] == 0.0


@pytest.mark.asyncio
async def test_base_provider_generate_for_capability(base_provider):
    """Тест генерации для capability."""
    await base_provider.initialize()
    
    # Создаем тестовые capability
    capabilities = [
        Capability(
            name="test.capability1",
            description="Тестовая capability 1",
            parameters_schema={"type": "object", "properties": {"param1": {"type": "string"}}},
            skill_name="test_skill"
        ),
        Capability(
            name="test.capability2",
            description="Тестовая capability 2",
            parameters_schema={"type": "object", "properties": {"param2": {"type": "string"}}},
            skill_name="test_skill"
        )
    ]
    
    mock_response = LLMResponse(
        content={
            "capability_name": "test.capability1",
            "parameters": {"param1": "value1"}
        },
        model=base_provider.model_name,
        tokens_used=10,
        generation_time=0.1,
        finish_reason="stop"
    )
    with patch.object(base_provider, 'generate_structured', return_value=mock_response) as mock_generate:
        result = await base_provider.generate_for_capability(
            system_prompt="Test system prompt",
            user_input="Test user input",
            capabilities=capabilities
        )
        
        mock_generate.assert_called_once()
        # Поскольку теперь возвращается LLMResponse, нам нужно получить content
        call_args = mock_generate.call_args
        assert result == ("test.capability1", {"param1": "value1"})


def test_base_provider_update_metrics(base_provider):
    """Тест обновления метрик."""
    # Первоначальные метрики
    assert base_provider.request_count == 0
    assert base_provider.error_count == 0
    assert base_provider.avg_response_time == 0.0
    
    # Обновляем метрики для успешного запроса
    base_provider._update_metrics(0.5, success=True)
    assert base_provider.request_count == 1
    assert base_provider.error_count == 0
    assert base_provider.avg_response_time > 0
    
    # Обновляем метрики для неуспешного запроса
    base_provider._update_metrics(0.3, success=False)
    assert base_provider.request_count == 2
    assert base_provider.error_count == 1
    assert base_provider.avg_response_time > 0
    
    # Проверяем обновление состояния здоровья
    for _ in range(10):
        base_provider._update_metrics(0.1, success=False)
    
    assert base_provider.health_status == LLMHealthStatus.DEGRADED