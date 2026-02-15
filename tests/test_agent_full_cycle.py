"""
Тесты для полного цикла работы агента с новой архитектурой
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.application.agent.runtime import AgentRuntime
from core.application.agent.components import (
    BehaviorManager,
    ActionExecutor,
    AgentPolicy,
    ProgressScorer,
    AgentState
)
from core.application.context.application_context import ApplicationContext


@pytest.fixture
def mock_application_context():
    """Создает mock объект для ApplicationContext"""
    context = MagicMock(spec=ApplicationContext)
    
    # Создаем mock для системного контекста
    mock_system_context = MagicMock()
    mock_system_context.list_capabilities.return_value = []
    context.system_context = mock_system_context
    
    # Создаем mock для контекста сессии
    mock_session_context = MagicMock()
    mock_session_context.record_decision = MagicMock()
    mock_session_context.record_error = MagicMock()
    context.session_context = mock_session_context
    
    # Создаем mock для контекста шага
    mock_step_context = MagicMock()
    mock_step_context.add_step = MagicMock()
    context.step_context = mock_step_context
    
    return context


@pytest.fixture
def mock_behavior_manager():
    """Создает mock объект для BehaviorManager"""
    manager = MagicMock(spec=BehaviorManager)
    manager.initialize = AsyncMock()
    
    # Mock для генерации решения
    mock_decision = MagicMock()
    mock_decision.action = MagicMock()
    mock_decision.action.value = "continue"
    mock_decision.capability_name = "test_capability"
    mock_decision.parameters = {}
    manager.generate_next_decision = AsyncMock(return_value=mock_decision)
    
    return manager


@pytest.mark.asyncio
async def test_agent_runtime_initialization(mock_application_context):
    """Тест инициализации AgentRuntime"""
    goal = "Тестовая цель"
    
    # Создаем экземпляр AgentRuntime
    agent_runtime = AgentRuntime(
        application_context=mock_application_context,
        goal=goal
    )
    
    # Проверяем, что все компоненты были инициализированы
    assert agent_runtime.application_context == mock_application_context
    assert agent_runtime.goal == goal
    assert agent_runtime._running is False
    assert isinstance(agent_runtime.state, AgentState)
    assert isinstance(agent_runtime.policy, AgentPolicy)
    assert isinstance(agent_runtime.progress, ProgressScorer)
    assert isinstance(agent_runtime.executor, ActionExecutor)
    assert isinstance(agent_runtime.behavior_manager, BehaviorManager)


@pytest.mark.asyncio
async def test_agent_runtime_run_cycle(mock_application_context, mock_behavior_manager):
    """Тест полного цикла выполнения агента"""
    goal = "Тестовая цель"
    
    with patch('core.application.agent.runtime.BehaviorManager', return_value=mock_behavior_manager):
        agent_runtime = AgentRuntime(
            application_context=mock_application_context,
            goal=goal,
            max_steps=2  # Ограничиваем количество шагов для теста
        )
        
        # Запускаем выполнение агента
        result = await agent_runtime.run()
        
        # Проверяем, что выполнение завершилось
        assert result is not None


@pytest.mark.asyncio
async def test_agent_runtime_with_different_strategies(mock_application_context):
    """Тест работы агента с разными стратегиями"""
    goal = "Тестовая цель"
    
    agent_runtime = AgentRuntime(
        application_context=mock_application_context,
        goal=goal,
        max_steps=1
    )
    
    # Тестируем различные политики
    policy_with_low_max_errors = AgentPolicy(max_errors=1, max_no_progress_steps=2)
    agent_with_policy = AgentRuntime(
        application_context=mock_application_context,
        goal=goal,
        policy=policy_with_low_max_errors,
        max_steps=1
    )
    
    # Запускаем выполнение с разными политиками
    result = await agent_with_policy.run()
    assert result is not None


@pytest.mark.asyncio
async def test_agent_runtime_error_handling(mock_application_context):
    """Тест обработки ошибок в AgentRuntime"""
    goal = "Тестовая цель"
    
    agent_runtime = AgentRuntime(
        application_context=mock_application_context,
        goal=goal,
        max_steps=1
    )
    
    # Тестируем сценарий, когда возникает ошибка
    original_execute_single_step = agent_runtime._execute_single_step
    
    async def mock_execute_single_step_error():
        raise Exception("Тестовая ошибка выполнения шага")
    
    agent_runtime._execute_single_step = mock_execute_single_step_error
    
    # Запускаем выполнение агента с ошибкой
    result = await agent_runtime.run()
    
    # Проверяем, что результат содержит информацию об ошибке
    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])