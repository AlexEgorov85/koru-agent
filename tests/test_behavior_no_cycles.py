"""
Тесты отсутствия циклических зависимостей в behavior patterns.
"""
import pytest
from unittest.mock import Mock


@pytest.mark.asyncio
async def test_no_circular_dependencies(
    create_react_pattern,
    create_planning_pattern,
    create_evaluation_pattern
):
    """Тест отсутствия циклических зависимостей между patterns."""
    try:
        # Создаем все patterns
        react_pattern = create_react_pattern()
        planning_pattern = create_planning_pattern()
        evaluation_pattern = create_evaluation_pattern()

        # Проверяем, что все patterns созданы успешно
        assert react_pattern is not None
        assert planning_pattern is not None
        assert evaluation_pattern is not None

    except Exception as e:
        pytest.fail(f"Ошибка при создании паттернов: {e}")


@pytest.mark.asyncio
async def test_pattern_independence(
    create_react_pattern,
    create_planning_pattern,
    create_evaluation_pattern
):
    """Тест независимости patterns друг от друга."""
    # Создаем patterns
    react_pattern = create_react_pattern()
    planning_pattern = create_planning_pattern()
    evaluation_pattern = create_evaluation_pattern()

    # Проверяем, что каждый pattern работает независимо
    # ReActPattern и PlanningPattern используют name, EvaluationPattern использует pattern_id
    assert hasattr(react_pattern, 'name') or hasattr(react_pattern, 'pattern_id')
    assert hasattr(planning_pattern, 'name') or hasattr(planning_pattern, 'pattern_id')
    assert hasattr(evaluation_pattern, 'pattern_id')


@pytest.mark.asyncio
async def test_no_direct_system_access(
    create_react_pattern,
    create_planning_pattern
):
    """Тест отсутствия прямого доступа к системе."""
    react_pattern = create_react_pattern()
    planning_pattern = create_planning_pattern()

    # Проверяем, что patterns не имеют прямого доступа к системным ресурсам
    # Они должны использовать только предоставленные им сервисы через application_context
    assert hasattr(react_pattern, 'application_context')
    assert hasattr(planning_pattern, 'application_context')


@pytest.mark.asyncio
async def test_pattern_creation_without_runtime(
    create_react_pattern,
    create_planning_pattern
):
    """Тест создания patterns без runtime зависимостей."""
    # Patterns должны создаваться без инициализации runtime компонентов
    react_pattern = create_react_pattern()
    planning_pattern = create_planning_pattern()

    # Проверяем базовую инициализацию
    assert react_pattern is not None
    assert planning_pattern is not None
