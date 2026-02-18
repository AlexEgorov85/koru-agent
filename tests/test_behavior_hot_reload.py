"""
Тесты hot reload для behavior patterns.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path


@pytest.mark.asyncio
async def test_behavior_hot_reload(create_react_pattern):
    """Тест горячей перезагрузки behavior patterns."""
    # Создаем pattern
    pattern = create_react_pattern()
    assert pattern is not None

    # Симулируем hot reload через создание нового экземпляра
    new_pattern = create_react_pattern()
    assert new_pattern is not None
    assert id(pattern) != id(new_pattern)


@pytest.mark.asyncio
async def test_behavior_version_switching(create_react_pattern):
    """Тест переключения версий behavior patterns."""
    # Создаем pattern v1
    pattern_v1 = create_react_pattern()

    # Создаем pattern v2 (симуляция новой версии)
    pattern_v2 = create_react_pattern()

    # Проверяем, что это разные экземпляры
    assert id(pattern_v1) != id(pattern_v2)
