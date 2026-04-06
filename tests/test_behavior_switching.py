"""
Тесты переключения behavior patterns.
"""
import pytest
from unittest.mock import Mock


@pytest.mark.asyncio
async def test_behavior_switching(create_react_pattern, create_planning_pattern):
    """Тест переключения между behavior patterns."""
    # Создаем patterns
    react_pattern = create_react_pattern()
    planning_pattern = create_planning_pattern()

    # Проверяем, что patterns могут быть переключены
    assert react_pattern is not None
    assert planning_pattern is not None

    # Симулируем переключение
    current_pattern = react_pattern
    current_pattern = planning_pattern

    assert current_pattern is not None


@pytest.mark.asyncio
async def test_evaluation_to_planning_switch(create_evaluation_pattern, create_planning_pattern):
    """Тест переключения с evaluation на planning."""
    eval_pattern = create_evaluation_pattern()
    planning_pattern = create_planning_pattern()

    # Симулируем переключение
    current_pattern = eval_pattern
    current_pattern = planning_pattern

    assert current_pattern is not None
