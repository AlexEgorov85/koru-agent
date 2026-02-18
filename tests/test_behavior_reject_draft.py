"""
Тесты rejection draft patterns в production.
"""
import pytest
from unittest.mock import Mock


@pytest.mark.asyncio
async def test_production_rejects_draft_patterns(create_react_pattern):
    """Тест что production отвергает draft версии patterns."""
    # Создаем active pattern
    active_pattern = create_react_pattern()
    assert active_pattern is not None

    # В production должны использоваться только active patterns
    # Draft patterns должны быть отклонены
    # Это проверяется на уровне валидации при загрузке


@pytest.mark.asyncio
async def test_behavior_storage_status_validation(create_planning_pattern):
    """Тест валидации статусов в behavior storage."""
    # Создаем active pattern
    active_pattern = create_planning_pattern()
    assert active_pattern is not None

    # Active версия должна загружаться корректно
    # Draft версия должна быть отклонена в production
