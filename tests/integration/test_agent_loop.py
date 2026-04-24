"""
Интеграционные тесты для цикла агента.

Проверяют взаимодействие всех фаз: Policy, Decision, Execution, Observer, ContextUpdate.
Используют MockLLMProvider для детерминированного тестирования.
"""

import pytest
import pytest_asyncio
from typing import Dict, Any
from pathlib import Path

from tests.mocks.mock_llm_provider import MockLLMProvider


@pytest.fixture
def fixtures_dir() -> Path:
    """Возвращает путь к директории с фикстурами."""
    return Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def mock_provider_default(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер со стандартным сценарием."""
    provider = MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="default"
    )
    return provider


@pytest.fixture
def mock_provider_error_recovery(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер со сценарием восстановления после ошибки."""
    provider = MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="error_recovery"
    )
    return provider


@pytest.fixture
def mock_provider_context_compression(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер с длинным сценарием для тестирования сжатия контекста."""
    provider = MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="context_compression"
    )
    return provider


class TestMockLLMProvider:
    """Базовые тесты MockLLMProvider."""

    @pytest.mark.asyncio
    async def test_mock_provider_initialization(self):
        """Тест инициализации mock провайдера."""
        provider = MockLLMProvider(
            response_sequence=[
                {"type": "finish", "answer": "Test", "confidence": 1.0}
            ]
        )
        
        await provider.initialize()
        
        assert provider.health_status == "healthy"
        assert provider.get_call_count() == 0

    @pytest.mark.asyncio
    async def test_mock_provider_generate_act(self):
        """Тест генерации ответа типа act."""
        from core.models.types.llm_types import LLMRequest
        
        provider = MockLLMProvider(
            response_sequence=[
                {
                    "type": "act",
                    "action": "sql_tool.execute",
                    "parameters": {"query": "SELECT 1"},
                    "reasoning": "Test query"
                }
            ]
        )
        await provider.initialize()
        
        request = LLMRequest(prompt="test", max_tokens=100)
        response = await provider.generate(request)
        
        assert response.finish_reason == "stop"
        assert "sql_tool.execute" in response.content
        assert provider.get_call_count() == 1

    @pytest.mark.asyncio
    async def test_mock_provider_generate_finish(self):
        """Тест генерации ответа типа finish."""
        from core.models.types.llm_types import LLMRequest
        
        provider = MockLLMProvider(
            response_sequence=[
                {"type": "finish", "answer": "Done", "confidence": 0.95}
            ]
        )
        await provider.initialize()
        
        request = LLMRequest(prompt="test", max_tokens=100)
        response = await provider.generate(request)
        
        assert response.finish_reason == "stop"
        assert response.content == "Done"
        assert provider.get_call_count() == 1

    @pytest.mark.asyncio
    async def test_mock_provider_generate_error(self):
        """Тест генерации ответа типа error."""
        from core.models.types.llm_types import LLMRequest
        
        provider = MockLLMProvider(
            response_sequence=[
                {
                    "type": "error",
                    "error": "Table not found",
                    "retry": True,
                    "suggestion": "Check table name"
                }
            ]
        )
        await provider.initialize()
        
        request = LLMRequest(prompt="test", max_tokens=100)
        response = await provider.generate(request)
        
        assert response.finish_reason == "error"
        assert "Table not found" in str(response.metadata)
        assert provider.get_call_count() == 1

    @pytest.mark.asyncio
    async def test_mock_provider_reset(self):
        """Тест сброса счётчика вызовов."""
        from core.models.types.llm_types import LLMRequest
        
        provider = MockLLMProvider(
            response_sequence=[
                {"type": "finish", "answer": "Done", "confidence": 0.9}
            ]
        )
        await provider.initialize()
        
        request = LLMRequest(prompt="test", max_tokens=100)
        await provider.generate(request)
        assert provider.get_call_count() == 1
        
        provider.reset()
        assert provider.get_call_count() == 0
        
        # Можно вызвать снова
        await provider.generate(request)
        assert provider.get_call_count() == 1


class TestMockScenarios:
    """Тесты сценариев из фикстур."""

    @pytest.mark.asyncio
    async def test_default_scenario(self, mock_provider_default: MockLLMProvider):
        """Тест стандартного сценария из default.json."""
        await mock_provider_default.initialize()
        
        assert mock_provider_default.scenario == "default"
        assert len(mock_provider_default.response_sequence) == 3  # 2 act + 1 finish

    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self, mock_provider_error_recovery: MockLLMProvider):
        """Тест сценария восстановления после ошибки."""
        await mock_provider_error_recovery.initialize()
        
        assert mock_provider_error_recovery.scenario == "error_recovery"
        assert len(mock_provider_error_recovery.response_sequence) >= 3

    @pytest.mark.asyncio
    async def test_context_compression_scenario(self, mock_provider_context_compression: MockLLMProvider):
        """Тест сценария для сжатия контекста."""
        await mock_provider_context_compression.initialize()
        
        assert mock_provider_context_compression.scenario == "context_compression"
        assert len(mock_provider_context_compression.response_sequence) >= 20
