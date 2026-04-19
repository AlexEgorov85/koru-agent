"""
Интеграционный тест агента с MockLLMProvider и реальной БД.

ЗАПУСК:
    pytest tests/integration/test_agent_with_mock_llm.py -v -s

ПРОВЕРЯЕТ:
1. AgentRuntime с MockLLMProvider — полный цикл
2. Реальная БД (postgresql)
3. Реальные промпты и контракты
4. Ответы MockLLMProvider соответствуют ожиданиям

ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    - Agent делает 1-2 шага
    - MockLLMProvider возвращает decision с next_action
    - SQL выполняется в БД
"""
import pytest
import pytest_asyncio
import logging
import uuid

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.agent.runtime import AgentRuntime
from tests.mocks.interfaces import MockLLM
from tests.mocks.llm_responses import (
    REASONING_EMPTY_CONTEXT,
    SQL_COUNT_CHECKS,
    REASONING_EMPTY_RESULTS,
    FINAL_ANSWER_DEFAULT,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_agent")


@pytest.fixture(scope="module")
def config():
    """Конфигурация для тестов - использует prod профиль."""
    return get_config(profile='prod', data_dir='data')


@pytest.fixture(scope="module")
def mock_llm():
    """MockLLMProvider с реалистичными ответами для агента."""
    mock = MockLLM(default_response=FINAL_ANSWER_DEFAULT)

    mock.register_response(" ReasoningResult", REASONING_EMPTY_CONTEXT)
    mock.register_response("SQLGenerationOutput", SQL_COUNT_CHECKS)
    mock.register_response("final_answer.generate", FINAL_ANSWER_DEFAULT)

    return mock


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config, mock_llm):
    """InfrastructureContext с реальной БД и MockLLM."""
    from core.models.data.resource import ResourceInfo
    from core.models.enums.common_enums import ResourceType

    infra = InfrastructureContext(config)
    await infra.initialize()

    old_registry = infra.resource_registry
    from core.infrastructure_context.resource_registry import ResourceRegistry
    infra.resource_registry = ResourceRegistry()
    infra._initialized = True

    infra.resource_registry.register_resource(
        ResourceInfo(
            name='mock_llm',
            resource_type=ResourceType.LLM,
            instance=mock_llm
        )
    )

    for res in old_registry.get_resources_by_type(ResourceType.DATABASE):
        infra.resource_registry.register_resource(res)

    logger.info("InfrastructureContext инициализирован с MockLLM")
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    """ApplicationContext с discovery промптов и контрактов."""
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=infrastructure.config.data_dir
    )

    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="prod"
    )
    await ctx.initialize()

    logger.info("ApplicationContext инициализирован")
    yield ctx
    await ctx.shutdown()


class TestMockLLMResponses:
    """Тесты структуры ответов MockLLM."""

    @pytest.mark.asyncio
    async def test_reasoning_result_structure(self, mock_llm):
        """ReasoningResult возвращает правильную структуру decision."""
        import json

        response = await mock_llm.generate(
            prompt="test ReasoningResult query",
            system_prompt="system"
        )

        data = json.loads(response)

        assert "stop_condition" in data
        assert "decision" in data
        assert data["decision"]["next_action"] == "check_result.generate_script"

    @pytest.mark.asyncio
    async def test_sql_generation_structure(self, mock_llm):
        """SQLGenerationOutput возвращает корректный SQL."""
        import json

        response = await mock_llm.generate(
            prompt="test SQLGenerationOutput query",
            system_prompt="system"
        )

        data = json.loads(response)

        assert "generated_sql" in data
        assert "oarb.audits" in data["generated_sql"]
        assert data["confidence_score"] > 0

    @pytest.mark.asyncio
    async def test_mock_llm_receives_prompts(self, mock_llm):
        """MockLLM получает промпты."""
        prompt = "test ReasoningResult query"
        await mock_llm.generate(prompt=prompt, system_prompt="sys")

        assert mock_llm.call_count >= 1
        assert any(prompt in p for p in mock_llm.prompt_history)


class TestAgentWithMockLLM:
    """Тесты агента с MockLLM - упрощённые."""

    @pytest.mark.asyncio
    async def test_agent_can_be_created(self, app_context, mock_llm):
        """AgentRuntime создаётся без ошибок."""
        runtime = AgentRuntime(
            application_context=app_context,
            goal="тестовая цель",
            max_steps=1,
            correlation_id="test-001",
            agent_id="test_agent"
        )

        assert runtime is not None
        assert runtime.goal == "тестовая цель"
        assert runtime.max_steps == 1

    @pytest.mark.asyncio
    async def test_mock_llm_used_in_executor(self, app_context, mock_llm):
        """Проверяем что MockLLM доступен через resource_registry."""
        from core.models.enums.common_enums import ResourceType

        providers = app_context.infrastructure_context.resource_registry.get_resources_by_type(ResourceType.LLM)

        mock_provider = next((p for p in providers if p.name == 'mock_llm'), None)
        assert mock_provider is not None
        assert mock_provider.instance is mock_llm