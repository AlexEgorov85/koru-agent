import pytest
from unittest.mock import AsyncMock, MagicMock
from core.agent_runtime.strategies.planning.strategy import PlanningStrategy
from core.agent_runtime.runtime import AgentRuntime
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus

@pytest.mark.asyncio
async def test_planning_strategy_filters_capabilities():
    """PlanningStrategy видит только capability с supported_strategies=['planning']"""
    # Моки
    system_mock = MagicMock()
    system_mock.list_capabilities.return_value = [
        Capability(
            name="planning.create_plan",
            description="test",
            parameters_schema={},
            skill_name="planning",
            supported_strategies=["planning"]
        ),
        Capability(
            name="book_library.get_books",
            description="test",
            parameters_schema={},
            skill_name="book_library",
            supported_strategies=["react", "planning"]  # ← Доступен для обеих
        ),
        Capability(
            name="react_only.skill",
            description="test",
            parameters_schema={},
            skill_name="test",
            supported_strategies=["react"]  # ← НЕ доступен для планирования
        )
    ]
    
    runtime_mock = MagicMock()
    runtime_mock.system = system_mock
    
    # Тест
    strategy = PlanningStrategy()
    caps = await strategy._get_available_capabilities(runtime_mock)
    
    # Проверки
    assert len(caps) == 2  # planning.create_plan + book_library.get_books (оба поддерживают planning)
    assert "planning.create_plan" in [c.name for c in caps]
    assert "book_library.get_books" in [c.name for c in caps]
    assert "react_only.skill" not in [c.name for c in caps]

@pytest.mark.asyncio
async def test_react_strategy_filters_capabilities():
    """ReActStrategy НЕ видит capability только для планирования"""
    from core.agent_runtime.strategies.react.strategy import ReActStrategy
    
    system_mock = MagicMock()
    system_mock.list_capabilities.return_value = [
        Capability(
            name="planning.create_plan",
            description="test",
            parameters_schema={},
            skill_name="planning",
            supported_strategies=["planning"]  # ← ТОЛЬКО для планирования
        ),
        Capability(
            name="book_library.get_books",
            description="test",
            parameters_schema={},
            skill_name="book_library",
            supported_strategies=["react", "planning"]
        )
    ]
    
    runtime_mock = MagicMock()
    runtime_mock.system = system_mock
    
    strategy = ReActStrategy()
    caps = await strategy._get_available_capabilities(runtime_mock)
    
    # Проверки
    assert len(caps) == 1  # Только book_library.get_books (supports react)
    assert "book_library.get_books" in [c.name for c in caps]
    assert "planning.create_plan" not in [c.name for c in caps]

@pytest.mark.asyncio
async def test_planning_strategy_creates_plan_when_missing():
    """PlanningStrategy создает план при отсутствии текущего плана"""
    strategy = PlanningStrategy()
    
    # Создаем моки
    session_mock = MagicMock()
    session_mock.get_current_plan.return_value = None
    session_mock.get_goal.return_value = "Запланируй поездку в Париж"
    
    # Создаем capability мок
    capability_mock = MagicMock()
    capability_mock.name = "planning.create_plan"
    
    system_mock = MagicMock()
    system_mock.get_capability.return_value = capability_mock
    
    runtime_mock = AsyncMock()
    runtime_mock.session = session_mock
    runtime_mock.system = system_mock
    
    decision = await strategy.next_step(runtime_mock)
    
    assert decision.action.value == "act"  # используем .value, так как это Enum
    assert decision.capability.name == "planning.create_plan"
    assert "goal" in decision.payload
    assert decision.payload["goal"] == "Запланируй поездку в Париж"

@pytest.mark.asyncio
async def test_planning_strategy_gets_next_step_when_plan_exists():
    """PlanningStrategy получает следующий шаг когда план существует"""
    strategy = PlanningStrategy()
    
    # Создаем моки
    plan_mock = MagicMock()
    plan_mock.item_id = "plan_123"
    
    session_mock = MagicMock()
    session_mock.get_current_plan.return_value = plan_mock
    
    # Имитация успешного получения следующего шага
    next_step_result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        result={"step_id": "step_1", "description": "Купить билеты"},
        observation_item_id=None,
        summary="Следующий шаг: купить билеты",
        error=None
    )
    
    executor_mock = AsyncMock()
    executor_mock.execute_capability.return_value = next_step_result
    
    capability_mock = MagicMock()
    
    system_mock = MagicMock()
    system_mock.get_capability.return_value = capability_mock
    
    runtime_mock = AsyncMock()
    runtime_mock.session = session_mock
    runtime_mock.executor = executor_mock
    runtime_mock.system = system_mock
    
    # Вызов метода получения шага (внутренний метод)
    result = await strategy._get_next_step_from_plan(runtime_mock, session_mock)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.result["step_id"] == "step_1"