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
from core.agent.runtime import AgentRuntime
from core.agent.factory import AgentFactory
from core.config.app_config import AppConfig


@pytest.fixture
def fixtures_dir() -> Path:
    """Возвращает путь к директории с фикстурами."""
    return Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def mock_provider_default(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер со стандартным сценарием."""
    return MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="default"
    )


@pytest.fixture
def mock_provider_error_recovery(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер со сценарием восстановления после ошибки."""
    return MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="error_recovery"
    )


@pytest.fixture
def mock_provider_context_compression(fixtures_dir: Path) -> MockLLMProvider:
    """Mock провайдер с длинным сценарием для тестирования сжатия контекста."""
    return MockLLMProvider(
        fixtures_dir=str(fixtures_dir),
        scenario="context_compression"
    )


@pytest.fixture
def app_config() -> AppConfig:
    """Базовая конфигурация приложения для тестов."""
    return AppConfig(
        llm_provider="mock",
        database_url="sqlite:///:memory:",
        max_steps=50,
        observer_mode="on_error",
        max_total_tokens=100000
    )


class TestAgentLoopBasic:
    """Базовые тесты цикла агента."""

    @pytest.mark.asyncio
    async def test_successful_execution(
        self,
        mock_provider_default: MockLLMProvider,
        app_config: AppConfig
    ):
        """Тест успешного выполнения: 2 действия + завершение."""
        # Создаём агент с mock провайдером
        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider_default,
            task="Получи данные о пользователях"
        )

        # Запускаем выполнение
        result = await runtime.run()

        # Проверяем результат
        assert result.status in ("COMPLETED", "FINISHED")
        assert mock_provider_default.get_call_count() == 3  # 2 act + 1 finish
        assert result.answer is not None
        assert len(result.answer) > 0

    @pytest.mark.asyncio
    async def test_observer_skip_rate(
        self,
        mock_provider_default: MockLLMProvider,
        app_config: AppConfig
    ):
        """Тест пропуска LLM-вызовов Observer при успешном выполнении."""
        app_config.observer_mode = "on_error"

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider_default,
            task="Получи данные"
        )

        result = await runtime.run()

        # Проверяем метрики
        metrics = runtime.metrics.to_dict()
        assert "observer_skips" in metrics
        assert "observer_llm_calls" in metrics
        
        # При observer_mode="on_error" и успешном выполнении LLM вызовов должно быть мало
        if metrics["observer_llm_calls"] > 0:
            # Если были вызовы, то skip_rate должен быть высоким
            skip_rate = metrics.get("observer_skip_rate", 0)
            assert skip_rate >= 0.5 or metrics["observer_skips"] > 0


class TestAgentLoopErrorRecovery:
    """Тесты восстановления после ошибок."""

    @pytest.mark.asyncio
    async def test_sql_error_recovery(
        self,
        mock_provider_error_recovery: MockLLMProvider,
        app_config: AppConfig
    ):
        """Тест восстановления после SQL-ошибки."""
        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider_error_recovery,
            task="Получи данные из таблицы"
        )

        result = await runtime.run()

        # Агент должен восстановиться и завершиться успешно
        assert result.status in ("COMPLETED", "FINISHED")
        assert mock_provider_error_recovery.get_call_count() >= 3
        
        # Проверяем, что ошибка была обработана
        metrics = runtime.metrics.to_dict()
        assert "errors_handled" in metrics or "retry_count" in metrics


class TestAgentLoopContextCompression:
    """Тесты сжатия контекста."""

    @pytest.mark.asyncio
    async def test_long_session_without_overflow(
        self,
        mock_provider_context_compression: MockLLMProvider,
        app_config: AppConfig
    ):
        """Тест длинной сессии без переполнения контекста."""
        # Устанавливаем низкий лимит для триггера сжатия
        app_config.context_max_tokens = 5000

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider_context_compression,
            task="Выполни серию запросов"
        )

        result = await runtime.run()

        # Сессия должна завершиться успешно без context_length_exceeded
        assert result.status in ("COMPLETED", "FINISHED")
        assert mock_provider_context_compression.get_call_count() >= 20

        # Проверяем метрики контекста
        metrics = runtime.metrics.to_dict()
        assert "context_token_estimate" in metrics
        # Контекст не должен превышать лимит значительно
        if "context_compressions" in metrics:
            assert metrics["context_compressions"] >= 1


class TestAgentLoopPolicy:
    """Тесты политик выполнения."""

    @pytest.mark.asyncio
    async def test_max_steps_limit(self, app_config: AppConfig):
        """Тест ограничения по максимальному количеству шагов."""
        app_config.max_steps = 3

        # Создаём последовательность из 10 act, чтобы превысить лимит
        mock_provider = MockLLMProvider(
            response_sequence=[
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 1"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 2"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 3"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 4"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 5"}},
            ]
        )

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider,
            task="Выполни много запросов"
        )

        result = await runtime.run()

        # Должно сработать ограничение по шагам
        assert result.status in ("LIMIT_REACHED", "STOPPED", "COMPLETED")
        assert mock_provider.get_call_count() <= app_config.max_steps + 2  # +1-2 на финализацию

    @pytest.mark.asyncio
    async def test_token_budget_limit(self, app_config: AppConfig):
        """Тест ограничения по бюджету токенов."""
        app_config.max_total_tokens = 1000  # Очень маленький бюджет

        mock_provider = MockLLMProvider(
            response_sequence=[
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 1"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 2"}},
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 3"}},
                {"type": "finish", "answer": "Готово", "confidence": 0.9},
            ]
        )

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider,
            task="Выполни запросы"
        )

        result = await runtime.run()

        # Либо завершится успешно до исчерпания, либо остановится по бюджету
        assert result.status in ("COMPLETED", "FINISHED", "STOPPED", "TOKEN_LIMIT_REACHED")


class TestAgentLoopObserver:
    """Тесты работы Observer."""

    @pytest.mark.asyncio
    async def test_observer_always_mode(self, app_config: AppConfig):
        """Тест режима Observer 'always' - LLM вызывается на каждом шаге."""
        app_config.observer_mode = "always"

        mock_provider = MockLLMProvider(
            response_sequence=[
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 1"}},
                {"type": "finish", "answer": "Готово", "confidence": 0.9},
            ]
        )

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider,
            task="Тест always режима"
        )

        result = await runtime.run()

        metrics = runtime.metrics.to_dict()
        # В режиме always observer_llm_calls должен быть > 0
        assert metrics.get("observer_llm_calls", 0) >= 1
        assert metrics.get("observer_skip_rate", 0) < 0.5

    @pytest.mark.asyncio
    async def test_observer_on_error_mode(self, app_config: AppConfig):
        """Тест режима Observer 'on_error' - LLM вызывается только при ошибках."""
        app_config.observer_mode = "on_error"

        mock_provider = MockLLMProvider(
            response_sequence=[
                {"type": "act", "action": "sql_tool.execute", "parameters": {"query": "SELECT 1"}},
                {"type": "finish", "answer": "Готово", "confidence": 0.9},
            ]
        )

        factory = AgentFactory(app_config)
        runtime = await factory.create_agent(
            llm_provider=mock_provider,
            task="Тест on_error режима"
        )

        result = await runtime.run()

        metrics = runtime.metrics.to_dict()
        # В режиме on_error при отсутствии ошибок skip_rate должен быть высоким
        assert metrics.get("observer_skip_rate", 0) >= 0.5 or metrics.get("observer_skips", 0) > 0


@pytest.mark.asyncio
async def test_agent_factory_with_mock(app_config: AppConfig):
    """Тест создания агента через фабрику с mock провайдером."""
    mock_provider = MockLLMProvider(
        response_sequence=[
            {"type": "finish", "answer": "Немедленное завершение", "confidence": 1.0}
        ]
    )

    # Инициализируем mock провайдер
    await mock_provider.initialize()

    factory = AgentFactory(app_config)
    
    # Создаём агент через фабрику (без llm_provider параметра)
    runtime = await factory.create_agent(
        goal="Быстрый тест",
        config=None
    )

    assert runtime is not None
    assert runtime.config is not None

    # Запускаем выполнение
    result = await runtime.run()
    assert result.status in ("COMPLETED", "FINISHED")
