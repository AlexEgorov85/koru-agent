"""
Юнит-тесты для OpenRouter провайдера.

Тестирует:
- Создание и инициализация провайдера
- Генерация текста (обычный и структурированный)
- Извлечение JSON из ответов
- Обработка ошибок
- Health check
- Shutdown
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any
from contextlib import asynccontextmanager

from core.infrastructure.providers.llm.openrouter_provider import (
    OpenRouterProvider,
    OpenRouterConfig
)
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    LLMHealthStatus,
    StructuredOutputConfig
)


class AsyncContextManagerMock:
    """Вспомогательный класс для моков async context manager."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class MockSession:
    """Вспомогательный класс для мока HTTP сессии."""

    def __init__(self, response_data=None, status=200, error_body=None):
        self._response_data = response_data
        self._status = status
        self._error_body = error_body

    def post(self, url, json=None):
        response = AsyncContextManagerMock(
            status=self._status,
            json=AsyncMock(return_value=self._response_data),
            text=AsyncMock(return_value=self._error_body or "")
        )
        return response


class TestOpenRouterConfig:
    """Тесты конфигурации OpenRouter."""

    def test_config_with_defaults(self):
        """Проверка: конфигурация создаётся с параметрами по умолчанию."""
        config = OpenRouterConfig(api_key="test-key")

        assert config.api_key == "test-key"
        assert config.model_name == "openai/gpt-4o-mini"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 120.0
        assert config.base_url == "https://openrouter.ai/api/v1/chat/completions"
        assert config.extra_headers == {}

    def test_config_with_custom_values(self):
        """Проверка: конфигурация принимает кастомные значения."""
        config = OpenRouterConfig(
            api_key="sk-or-v1-custom",
            model_name="anthropic/claude-3.5-sonnet",
            temperature=0.3,
            max_tokens=2048,
            timeout_seconds=60.0,
            extra_headers={"X-Custom": "value"}
        )

        assert config.api_key == "sk-or-v1-custom"
        assert config.model_name == "anthropic/claude-3.5-sonnet"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 60.0
        assert config.extra_headers == {"X-Custom": "value"}


class TestOpenRouterProviderCreation:
    """Тесты создания провайдера."""

    def test_create_with_config_object(self):
        """Проверка: провайдер создаётся с объектом конфигурации."""
        config = OpenRouterConfig(api_key="test-key", model_name="openai/gpt-4o-mini")
        provider = OpenRouterProvider(config=config)

        assert isinstance(provider, BaseLLMProvider)
        assert provider.model_name == "openai/gpt-4o-mini"
        assert provider.config_obj.api_key == "test-key"

    def test_create_with_dict_config(self):
        """Проверка: провайдер создаётся со словарём конфигурации."""
        config_dict = {
            "api_key": "test-key",
            "model_name": "google/gemini-pro",
            "temperature": 0.5
        }
        provider = OpenRouterProvider(config=config_dict)

        assert isinstance(provider, BaseLLMProvider)
        assert provider.model_name == "google/gemini-pro"
        assert provider.config_obj.temperature == 0.5

    def test_create_with_model_name_override(self):
        """Проверка: model_name переопределяется при передаче отдельно."""
        config = OpenRouterConfig(api_key="test-key", model_name="openai/gpt-4o-mini")
        provider = OpenRouterProvider(config=config, model_name="anthropic/claude-3")

        assert provider.model_name == "anthropic/claude-3"


class TestOpenRouterProviderInitialize:
    """Тесты инициализации провайдера."""

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self):
        """Проверка: инициализация создаёт HTTP сессию."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            result = await provider.initialize()

            assert result is True
            assert provider.is_initialized is True
            assert provider.health_status == LLMHealthStatus.HEALTHY
            mock_session_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_handles_error(self):
        """Проверка: инициализация обрабатывает ошибки gracefully."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
            result = await provider.initialize()

            assert result is False
            assert provider.health_status == LLMHealthStatus.UNHEALTHY


class TestOpenRouterProviderShutdown:
    """Тесты завершения работы провайдера."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_session(self):
        """Проверка: shutdown закрывает HTTP сессию."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        mock_session = AsyncMock()
        mock_session.closed = False
        provider._session = mock_session
        provider.is_initialized = True

        await provider.shutdown()

        mock_session.close.assert_awaited_once()
        assert provider._session is None
        assert provider.is_initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_no_session(self):
        """Проверка: shutdown не падает без сессии."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider._session = None

        await provider.shutdown()

        assert provider._session is None


class TestOpenRouterProviderHealthCheck:
    """Тесты проверки здоровья провайдера."""

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Проверка: health check для неинициализированного провайдера."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        result = await provider.health_check()

        assert result["status"] == LLMHealthStatus.UNHEALTHY.value
        assert "error" in result
        assert result["is_initialized"] is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Проверка: health check для здорового провайдера."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        provider._session = MockSession(status=200, response_data={"status": "ok"})

        result = await provider.health_check()

        assert result["status"] == LLMHealthStatus.HEALTHY.value
        assert result["is_initialized"] is True


class TestOpenRouterProviderGenerateImpl:
    """Тесты генерации текста."""

    @pytest.mark.asyncio
    async def test_generate_impl_success(self):
        """Проверка: успешная генерация текста."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {
            "choices": [
                {
                    "message": {"content": "Hello, world!"},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"total_tokens": 50}
        }

        provider._session = MockSession(status=200, response_data=mock_response_data)

        request = LLMRequest(
            prompt="Say hello",
            temperature=0.7,
            max_tokens=100
        )

        response = await provider._generate_impl(request)

        assert response.content == "Hello, world!"
        assert response.model == "openai/gpt-4o-mini"
        assert response.tokens_used == 50
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_impl_http_error(self):
        """Проверка: обработка HTTP ошибки."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        provider._session = MockSession(status=401, error_body='{"error": "Invalid API key"}')

        request = LLMRequest(prompt="Test", temperature=0.7, max_tokens=100)
        response = await provider._generate_impl(request)

        assert response.finish_reason == "error"
        assert "error" in response.metadata
        assert "401" in response.metadata["error"]

    @pytest.mark.asyncio
    async def test_generate_impl_empty_choices(self):
        """Проверка: обработка пустого ответа."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {"choices": [], "usage": {"total_tokens": 0}}

        provider._session = MockSession(status=200, response_data=mock_response_data)

        request = LLMRequest(prompt="Test", temperature=0.7, max_tokens=100)
        response = await provider._generate_impl(request)

        assert response.finish_reason == "error"
        assert response.content == ""

    @pytest.mark.asyncio
    async def test_generate_impl_structured_output(self):
        """Проверка: генерация с структурированным выводом."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {
            "choices": [
                {
                    "message": {"content": '{"name": "John", "age": 30}'},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"total_tokens": 40}
        }

        provider._session = MockSession(status=200, response_data=mock_response_data)

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }

        structured_output = StructuredOutputConfig(
            output_model="Person",
            schema_def=schema
        )

        request = LLMRequest(
            prompt="Extract person info",
            temperature=0.7,
            max_tokens=200,
            structured_output=structured_output
        )

        response = await provider._generate_impl(request)

        assert response.raw_response is not None
        assert response.raw_response.content == '{"name": "John", "age": 30}'
        assert response.parsing_attempts == 1
        assert response.validation_errors == []

    @pytest.mark.asyncio
    async def test_generate_impl_structured_output_invalid_json(self):
        """Проверка: структурированный вывод с невалидным JSON."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {
            "choices": [
                {
                    "message": {"content": "This is not JSON at all"},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"total_tokens": 30}
        }

        provider._session = MockSession(status=200, response_data=mock_response_data)

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        }

        structured_output = StructuredOutputConfig(
            output_model="Person",
            schema_def=schema
        )

        request = LLMRequest(
            prompt="Extract person",
            temperature=0.7,
            max_tokens=200,
            structured_output=structured_output
        )

        response = await provider._generate_impl(request)

        assert response.finish_reason == "stop"
        assert len(response.validation_errors) == 1
        assert response.validation_errors[0]["error"] == "json_parse_error"


class TestOpenRouterProviderJsonExtraction:
    """Тесты извлечения JSON из ответов."""

    def test_extract_json_from_markdown_block(self):
        """Проверка: извлечение JSON из markdown блока."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        content = '''Here is the JSON:
```json
{"name": "John", "age": 30}
```
That's it!'''

        result = provider._extract_json_from_response(content)
        assert result == '{"name": "John", "age": 30}'

    def test_extract_json_from_plain_text(self):
        """Проверка: извлечение JSON из обычного текста."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        content = '{"name": "John", "age": 30}'
        result = provider._extract_json_from_response(content)
        assert result == '{"name": "John", "age": 30}'

    def test_extract_json_with_surrounding_text(self):
        """Проверка: извлечение JSON с окружающим текстом."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        content = "Sure! Here is the data you requested:\n\n{\"name\": \"John\"}\n\nHope this helps!"
        result = provider._extract_json_from_response(content)
        assert result == '{"name": "John"}'

    def test_extract_json_from_code_block_without_language(self):
        """Проверка: извлечение JSON из code блока без указания языка."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        content = "```\n{\"key\": \"value\"}\n```"
        result = provider._extract_json_from_response(content)
        assert result == '{"key": "value"}'


class TestOpenRouterProviderBuildMessages:
    """Тесты построения сообщений."""

    def test_build_messages_with_system_and_user(self):
        """Проверка: построение сообщений с system и user ролями."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        request = LLMRequest(
            prompt="What is 2+2?",
            system_prompt="You are a math tutor."
        )

        messages = provider._build_messages(request)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a math tutor."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is 2+2?"

    def test_build_messages_with_user_only(self):
        """Проверка: построение сообщений только с user ролью."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        request = LLMRequest(prompt="Hello!")
        messages = provider._build_messages(request)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"


class TestOpenRouterProviderInterface:
    """Тесты LLMInterface методов."""

    @pytest.mark.asyncio
    async def test_generate_interface(self):
        """Проверка: метод generate из LLMInterface."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {
            "choices": [
                {"message": {"content": "42"}, "finish_reason": "stop"}
            ],
            "usage": {"total_tokens": 10}
        }

        provider._session = MockSession(status=200, response_data=mock_response_data)

        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is 2+2?"}
        ]

        result = await provider.generate(messages, temperature=0.5, max_tokens=50)

        assert result == "42"

    @pytest.mark.asyncio
    async def test_generate_structured_interface(self):
        """Проверка: метод generate_structured из LLMInterface."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)
        provider.is_initialized = True

        mock_response_data = {
            "choices": [
                {
                    "message": {"content": '{"result": 4}'},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"total_tokens": 20}
        }

        provider._session = MockSession(status=200, response_data=mock_response_data)

        messages = [{"role": "user", "content": "What is 2+2?"}]
        schema = {
            "type": "object",
            "properties": {"result": {"type": "integer"}},
            "required": ["result"]
        }

        result = await provider.generate_structured(messages, schema)

        assert result == {"result": 4}

    @pytest.mark.asyncio
    async def test_count_tokens(self):
        """Проверка: подсчёт токенов."""
        config = OpenRouterConfig(api_key="test-key")
        provider = OpenRouterProvider(config=config)

        messages = [
            {"role": "system", "content": "Hello world"},
            {"role": "user", "content": "How are you?"}
        ]

        result = await provider.count_tokens(messages)

        assert isinstance(result, int)
        assert result > 0


class TestOpenRouterProviderFactory:
    """Тесты создания через фабрику."""

    def test_factory_creates_openrouter_provider(self):
        """Проверка: фабрика создаёт OpenRouter провайдер."""
        from core.infrastructure.providers.llm.factory import LLMProviderFactory

        config = OpenRouterConfig(api_key="test-key")
        provider = LLMProviderFactory.create_provider('openrouter', config=config)

        assert isinstance(provider, OpenRouterProvider)
        assert isinstance(provider, BaseLLMProvider)

    def test_factory_with_dict_config(self):
        """Проверка: фабрика создаёт провайдер со словарём."""
        from core.infrastructure.providers.llm.factory import LLMProviderFactory

        config_dict = {
            "api_key": "test-key",
            "model_name": "anthropic/claude-3.5-sonnet"
        }
        provider = LLMProviderFactory.create_provider('openrouter', config=config_dict)

        assert isinstance(provider, OpenRouterProvider)
        assert provider.model_name == "anthropic/claude-3.5-sonnet"
