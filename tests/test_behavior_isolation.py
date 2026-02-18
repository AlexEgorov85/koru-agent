"""
Тесты изоляции behavior patterns.
"""
import pytest
from unittest.mock import Mock


@pytest.mark.asyncio
async def test_behavior_isolation(create_react_pattern, create_planning_pattern):
    """Тест изоляции между behavior patterns."""
    # Создаем два независимых экземпляра ReActPattern
    react_pattern_1 = create_react_pattern()
    react_pattern_2 = create_react_pattern()

    # Проверяем, что это разные объекты
    assert id(react_pattern_1) != id(react_pattern_2)

    # Создаем два независимых экземпляра PlanningPattern
    planning_pattern_1 = create_planning_pattern()
    planning_pattern_2 = create_planning_pattern()

    # Проверяем, что это разные объекты
    assert id(planning_pattern_1) != id(planning_pattern_2)

    # Проверяем, что patterns разных типов независимы
    assert type(react_pattern_1) != type(planning_pattern_1)


@pytest.mark.asyncio
async def test_multiple_agents_isolation(create_react_pattern, create_planning_pattern):
    """Тест изоляции между агентами с разными patterns."""
    # Агент 1 использует ReAct
    agent1_pattern = create_react_pattern()

    # Агент 2 использует Planning
    agent2_pattern = create_planning_pattern()

    # Проверяем изоляцию
    assert agent1_pattern is not None
    assert agent2_pattern is not None
    assert type(agent1_pattern) != type(agent2_pattern)
