"""
Тесты обработки пустых ответов от LLM.

ПРОВЕРЯЕТ:
1. BaseLLMProvider._validate_response_content()
2. LlamaCpp provider generated_text.strip()
3. LLMOrchestrator retry при empty_response
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.types.llm_types import (
    LLMResponse, RawLLMResponse, LLMRequest, StructuredOutputConfig
)


# ============================================================================
# 1. Тесты BaseLLMProvider._validate_response_content()
# ============================================================================

class TestValidateResponseContent:
    """Тесты валидации контента ответа."""

    def test_valid_content_content(self):
        """Ответ с непустым content — валиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(content="Привет, мир!", model="test")
        assert provider._validate_response_content(response) is True

    def test_valid_parsed_content(self):
        """Ответ с parsed_content — валиден (даже если content пуст)."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        class DummyModel:
            pass
        
        response = LLMResponse(
            content="",
            parsed_content=DummyModel(),
            model="test"
        )
        assert provider._validate_response_content(response) is True

    def test_valid_raw_response_content(self):
        """Ответ с непустым raw_response.content — валиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(
            content="",
            raw_response=RawLLMResponse(
                content='{"key": "value"}',
                model="test",
                tokens_used=10,
                generation_time=0.5
            ),
            model="test"
        )
        assert provider._validate_response_content(response) is True

    def test_empty_content_only_whitespace(self):
        """Content с только пробелами — невалиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(content="   \n\t  ", model="test")
        assert provider._validate_response_content(response) is False

    def test_empty_raw_response_content(self):
        """raw_response.content пустой — невалиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(
            content="",
            raw_response=RawLLMResponse(
                content="",
                model="test",
                tokens_used=0,
                generation_time=0.0
            ),
            model="test"
        )
        assert provider._validate_response_content(response) is False

    def test_completely_empty_response(self):
        """Полностью пустой ответ — невалиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(content="", model="test")
        assert provider._validate_response_content(response) is False

    def test_whitespace_only_raw_response(self):
        """raw_response.content только пробелы — невалиден."""
        from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
        config = MockLLMConfig(model_name="test-model")
        provider = MockLLMProvider(config=config)
        
        response = LLMResponse(
            content="",
            raw_response=RawLLMResponse(
                content="   \t\n  ",
                model="test",
                tokens_used=0,
                generation_time=0.0
            ),
            model="test"
        )
        assert provider._validate_response_content(response) is False


# ============================================================================
# Интеграционные тесты
# ============================================================================

class TestIntegrationEmptyResponse:
    """Интеграционные тесты обработки пустых ответов."""

    @pytest.mark.asyncio
    async def test_full_cycle_empty_response(self):
        """Provider → Orchestrator: пустой ответ → StructuredOutputError."""
        from core.infrastructure.providers.llm.llm_orchestrator import LLMOrchestrator
        from core.errors.exceptions import StructuredOutputError
        
        orchestrator = LLMOrchestrator(event_bus=AsyncMock())
        orchestrator._logger = MagicMock()
        orchestrator.executor = AsyncMock()
        orchestrator.executor.execute_action = AsyncMock()
        
        # Мокируем provider чтобы вернуть пустой ответ
        mock_provider = AsyncMock()
        
        async def mock_execute(*args, **kwargs):
            return LLMResponse(
                content="",
                raw_response=RawLLMResponse(
                    content="",
                    model="test",
                    tokens_used=0,
                    generation_time=0.0,
                    finish_reason="empty"
                ),
                model="test",
                finish_reason="empty"
            )
        
        request = LLMRequest(
            prompt="test",
            structured_output=StructuredOutputConfig(
                output_model="Test",
                schema_def={"type": "object", "properties": {}}
            )
        )
        
        # Orchestrator должен выбросить StructuredOutputError после retry
        with patch.object(orchestrator, 'execute', new_callable=AsyncMock, side_effect=mock_execute):
            with pytest.raises(StructuredOutputError):
                await orchestrator.execute_structured(
                    request=request,
                    provider=mock_provider,
                    max_retries=2
                )
