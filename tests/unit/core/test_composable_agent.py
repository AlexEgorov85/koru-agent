"""
Тесты для ComposableAgent - чистой реализации ComposableAgentInterface.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.composable_agent import ComposableAgent
from core.atomic_actions.base import AtomicAction, AtomicActionType
from core.composable_patterns.base import ComposablePattern, ConcreteComposablePattern
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext


class MockAtomicAction(AtomicAction):
    """Мок атомарного действия для тестирования."""
    
    def __init__(self, name: str = "mock_action", result_type: StrategyDecisionType = StrategyDecisionType.CONTINUE):
        super().__init__(name, "Mock atomic action for testing")
        self.result_type = result_type
    
    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=self.result_type, reason="mock_action_executed")


class MockComposablePattern(ComposablePattern):
    """Мок компонуемого паттерна для тестирования."""
    
    def __init__(self, name: str = "mock_pattern", result_type: StrategyDecisionType = StrategyDecisionType.CONTINUE):
        super().__init__(name, "Mock composable pattern for testing")
        self.result_type = result_type
    
    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=self.result_type, reason="mock_pattern_executed")


@pytest.mark.asyncio
async def test_composable_agent_initialization():
    """Тестирует инициализацию ComposableAgent."""
    agent = ComposableAgent("TestAgent", "Test agent for unit tests")
    
    assert agent.name == "TestAgent"
    assert agent.description == "Test agent for unit tests"
    assert agent.domains == []
    assert agent.runtime is None
    assert len(agent.get_available_domains()) > 0
    assert "general" in agent.get_available_domains()


@pytest.mark.asyncio
async def test_execute_atomic_action():
    """Тестирует выполнение атомарного действия."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    mock_action = MockAtomicAction()
    
    result = await agent.execute_atomic_action(mock_action, context)
    
    assert isinstance(result, StrategyDecision)
    assert result.reason == "mock_action_executed"


@pytest.mark.asyncio
async def test_execute_composable_pattern():
    """Тестирует выполнение компонуемого паттерна."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    mock_pattern = MockComposablePattern()
    
    result = await agent.execute_composable_pattern(mock_pattern, context)
    
    assert isinstance(result, StrategyDecision)
    assert result.reason == "mock_pattern_executed"


@pytest.mark.asyncio
async def test_adapt_to_domain():
    """Тестирует адаптацию к домену."""
    agent = ComposableAgent("TestAgent")
    initial_domains = agent.get_available_domains().copy()
    
    # Проверяем, что можно адаптироваться к существующему домену
    agent.adapt_to_domain("code_analysis")
    adapted_domains = agent.domains
    
    assert "code_analysis" in adapted_domains
    assert "code_analysis" in agent.get_available_domains()


@pytest.mark.asyncio
async def test_adapt_to_invalid_domain_raises_error():
    """Тестирует, что попытка адаптации к недоступному домену вызывает ошибку."""
    agent = ComposableAgent("TestAgent")
    
    with pytest.raises(ValueError, match="Domain 'invalid_domain' is not supported"):
        agent.adapt_to_domain("invalid_domain")


@pytest.mark.asyncio
async def test_get_available_domains_returns_copy():
    """Тестирует, что get_available_domains возвращает копию списка."""
    agent = ComposableAgent("TestAgent")
    domains1 = agent.get_available_domains()
    domains2 = agent.get_available_domains()
    
    # Должны быть разными объектами списков
    assert domains1 is not domains2
    # Но содержать одинаковые значения
    assert domains1 == domains2


@pytest.mark.asyncio
async def test_simple_composable_agent_initialization():
    """Тестирует инициализацию SimpleComposableAgent."""
    from core.composable_agent import SimpleComposableAgent
    
    # Без начального домена
    agent1 = SimpleComposableAgent("SimpleAgent1")
    assert agent1.name == "SimpleAgent1"
    assert agent1.domains == []
    
    # С начальным доменом
    agent2 = SimpleComposableAgent("SimpleAgent2", "Test simple agent", "general")
    assert agent2.name == "SimpleAgent2"
    assert "general" in agent2.domains
    assert agent2.description == "Test simple agent"


@pytest.mark.asyncio
async def test_simple_execute_with_atomic_action():
    """Тестирует простое выполнение с атомарным действием."""
    from core.composable_agent import SimpleComposableAgent
    
    agent = SimpleComposableAgent("SimpleAgent")
    context = {"test": "context"}
    mock_action = MockAtomicAction()
    
    result = await agent.simple_execute(mock_action, context)
    
    assert isinstance(result, StrategyDecision)
    assert result.reason == "mock_action_executed"


@pytest.mark.asyncio
async def test_simple_execute_with_composable_pattern():
    """Тестирует простое выполнение с компонуемым паттерном."""
    from core.composable_agent import SimpleComposableAgent
    
    agent = SimpleComposableAgent("SimpleAgent")
    context = {"test": "context"}
    mock_pattern = MockComposablePattern()
    
    result = await agent.simple_execute(mock_pattern, context)
    
    assert isinstance(result, StrategyDecision)
    assert result.reason == "mock_pattern_executed"


@pytest.mark.asyncio
async def test_simple_execute_with_invalid_type_raises_error():
    """Тестирует, что простое выполнение с неправильным типом вызывает ошибку."""
    from core.composable_agent import SimpleComposableAgent
    
    agent = SimpleComposableAgent("SimpleAgent")
    context = {"test": "context"}
    
    with pytest.raises(TypeError, match="Expected AtomicAction or ComposablePattern"):
        await agent.simple_execute("invalid_type", context)


@pytest.mark.asyncio
async def test_execute_atomic_action_with_parameters():
    """Тестирует выполнение атомарного действия с параметрами."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    parameters = {"param1": "value1", "param2": "value2"}
    mock_action = MockAtomicAction()
    
    # Мокаем метод execute у действия, чтобы проверить передачу параметров
    original_execute = mock_action.execute
    mock_action.execute = AsyncMock(return_value=await original_execute(None, context, parameters))
    
    result = await agent.execute_atomic_action(mock_action, context, parameters)
    
    # Проверяем, что execute был вызван с правильными параметрами
    mock_action.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_composable_pattern_with_parameters():
    """Тестирует выполнение компонуемого паттерна с параметрами."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    parameters = {"param1": "value1", "param2": "value2"}
    mock_pattern = MockComposablePattern()
    
    # Мокаем метод execute у паттерна, чтобы проверить передачу параметров
    original_execute = mock_pattern.execute
    mock_pattern.execute = AsyncMock(return_value=await original_execute(None, context, parameters))
    
    result = await agent.execute_composable_pattern(mock_pattern, context, parameters)
    
    # Проверяем, что execute был вызван с правильными параметрами
    mock_pattern.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_atomic_action_with_full_lifecycle():
    """Тестирует выполнение атомарного действия с полным жизненным циклом."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    mock_action = MockAtomicAction()
    
    # Так как метод требует полноценный runtime, мокируем его создание
    original_runtime = agent.runtime
    agent.runtime = AsyncMock()
    agent.runtime.session = MagicMock()
    agent.runtime.system = MagicMock()
    
    result = await agent.execute_atomic_action_with_full_lifecycle(mock_action, context)
    
    assert isinstance(result, StrategyDecision)
    # Проверяем, что результат содержит информацию о выполненном действии
    assert "executed_action" in result.payload
    assert result.payload["executed_action"] == "mock_action"


@pytest.mark.asyncio
async def test_execute_atomic_action_with_full_lifecycle_and_parameters():
    """Тестирует выполнение атомарного действия с полным жизненным циклом и параметрами."""
    agent = ComposableAgent("TestAgent")
    context = {"test": "context"}
    parameters = {"param1": "value1", "param2": "value2"}
    mock_action = MockAtomicAction()
    
    # Мокируем runtime
    agent.runtime = AsyncMock()
    agent.runtime.session = MagicMock()
    agent.runtime.system = MagicMock()
    
    result = await agent.execute_atomic_action_with_full_lifecycle(mock_action, context, parameters)
    
    assert isinstance(result, StrategyDecision)
    assert "executed_action" in result.payload
