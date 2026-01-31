"""
Тесты для модели LLMTypes (LLMRequest, LLMResponse, LLMHealthStatus, LLMProviderType).
"""
import pytest
from models.llm_types import LLMRequest, LLMResponse, LLMHealthStatus, LLMProviderType


def test_llm_request_creation():
    """Тест создания LLMRequest."""
    request = LLMRequest(
        prompt="Тестовый промпт",
        system_prompt="Системный промпт",
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.5
    )
    
    assert request.prompt == "Тестовый промпт"
    assert request.system_prompt == "Системный промпт"
    assert request.temperature == 0.7
    assert request.max_tokens == 2048
    assert request.top_p == 0.9
    assert request.frequency_penalty == 0.5
    assert request.presence_penalty == 0.5


def test_llm_request_with_optional_fields():
    """Тест создания LLMRequest с метаданными."""
    request = LLMRequest(
        prompt="Тестовый промпт",
        temperature=0.5,
        metadata={"response_format": {"type": "json_object"}, "test_param": "value"}
    )
    
    assert request.metadata == {"response_format": {"type": "json_object"}, "test_param": "value"}


def test_llm_request_default_values():
    """Тест значений по умолчанию для LLMRequest."""
    request = LLMRequest(
        prompt="Тестовый промпт"
    )
    
    assert request.system_prompt is None      # значение по умолчанию
    assert request.temperature == 0.7         # значение по умолчанию
    assert request.max_tokens == 500          # значение по умолчанию из модели
    assert request.top_p == 0.95              # значение по умолчанию
    assert request.frequency_penalty == 0.0   # значение по умолчанию
    assert request.presence_penalty == 0.0    # значение по умолчанию
    assert request.stream is False            # значение по умолчанию
    assert request.metadata == {}             # значение по умолчанию из __post_init__


def test_llm_request_parameter_validation():
    """Тест валидации параметров LLMRequest."""
    request = LLMRequest(
        prompt="Тестовый промпт",
        temperature=2.0,  # значение выше максимума
        max_tokens=5000,  # значение выше максимума
        top_p=1.5,       # значение выше максимума
        frequency_penalty=3.0,  # значение выше максимума
        presence_penalty=3.0    # значение выше максимума
    )
    
    # Проверяем, что значения были ограничены до максимально допустимых
    assert request.temperature == 1.0  # максимальное значение
    assert request.max_tokens == 4096  # максимальное значение
    assert request.top_p == 1.0        # максимальное значение
    assert request.frequency_penalty == 2.0  # максимальное значение
    assert request.presence_penalty == 2.0   # максимальное значение


def test_llm_response_creation():
    """Тест создания LLMResponse."""
    response = LLMResponse(
        content="Тестовый ответ",
        model="test-model",
        tokens_used=50,
        generation_time=0.5
    )
    
    assert response.content == "Тестовый ответ"
    assert response.model == "test-model"
    assert response.tokens_used == 50
    assert response.generation_time == 0.5


def test_llm_response_with_optional_fields():
    """Тест создания LLMResponse с дополнительными полями."""
    response = LLMResponse(
        content="Тестовый ответ",
        model="test-model",
        tokens_used=50,
        generation_time=0.5,
        finish_reason="stop",
        metadata={"usage": {"prompt_tokens": 20, "completion_tokens": 30}, "test_field": "value"}
    )
    
    assert response.finish_reason == "stop"
    assert response.metadata == {"usage": {"prompt_tokens": 20, "completion_tokens": 30}, "test_field": "value"}


def test_llm_response_default_values():
    """Тест значений по умолчанию для LLMResponse."""
    response = LLMResponse(
        content="Тестовый ответ",
        model="test-model",
        tokens_used=50,
        generation_time=0.5
    )
    
    assert response.finish_reason == "stop"  # значение по умолчанию
    assert response.metadata == {}           # значение по умолчанию из __post_init__


def test_llm_response_parameter_validation():
    """Тест валидации параметров LLMResponse."""
    response = LLMResponse(
        content="Тестовый ответ",
        model="test-model",
        tokens_used=-10,      # отрицательное значение
        generation_time=-0.5  # отрицательное значение
    )
    
    # Проверяем, что значения были нормализованы до минимально допустимых
    assert response.tokens_used >= 0        # минимальное значение
    assert response.generation_time >= 0.0  # минимальное значение


def test_llm_health_status_enum_values():
    """Тест значений LLMHealthStatus enum."""
    assert LLMHealthStatus.HEALTHY.value == "healthy"
    assert LLMHealthStatus.DEGRADED.value == "degraded"
    assert LLMHealthStatus.UNHEALTHY.value == "unhealthy"
    assert LLMHealthStatus.UNKNOWN.value == "unknown"
    
    # Проверяем все значения
    all_statuses = [status.value for status in LLMHealthStatus]
    expected_statuses = ["healthy", "degraded", "unhealthy", "unknown"]
    assert set(all_statuses) == set(expected_statuses)


def test_llm_provider_type_enum_values():
    """Тест значений LLMProviderType enum."""
    assert LLMProviderType.OPENAI.value == "openai"
    assert LLMProviderType.ANTHROPIC.value == "anthropic"
    assert LLMProviderType.LOCAL_LLAMA.value == "local_llama"
    assert LLMProviderType.GEMINI.value == "gemini"
    assert LLMProviderType.CUSTOM.value == "custom"
    
    # Проверяем все значения
    all_provider_types = [provider_type.value for provider_type in LLMProviderType]
    expected_provider_types = ["openai", "anthropic", "local_llama", "gemini", "custom"]
    assert set(all_provider_types) == set(expected_provider_types)


def test_llm_request_response_integration():
    """Тест интеграции LLMRequest и LLMResponse."""
    # Создаем запрос
    request = LLMRequest(
        prompt="Суммаризуй текст",
        system_prompt="Ты - помощник по суммаризации",
        temperature=0.3,
        max_tokens=100
    )
    
    # Создаем ответ
    response = LLMResponse(
        content="Краткое содержание текста...",
        model="gpt-4o-mini",
        tokens_used=45,
        generation_time=0.8,
        finish_reason="length"
    )
    
    # Проверяем, что оба объекта создались корректно
    assert request.prompt == "Суммаризуй текст"
    assert request.system_prompt == "Ты - помощник по суммаризации"
    assert request.temperature == 0.3
    assert request.max_tokens == 100
    
    assert response.content == "Краткое содержание текста..."
    assert response.model == "gpt-4o-mini"
    assert response.tokens_used == 45
    assert response.generation_time == 0.8
    assert response.finish_reason == "length"