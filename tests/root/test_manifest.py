"""Тесты модели Manifest."""
import pytest
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus


def test_valid_manifest_creation():
    """Проверка создания валидного манифеста."""
    m = Manifest(
        component_id='test',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='test_owner',
        status=ComponentStatus.ACTIVE
    )
    assert m.component_id == 'test'
    assert m.version == 'v1.0.0'
    assert m.component_type == ComponentType.SKILL


def test_invalid_version_rejected():
    """Проверка отклонения версии без префикса 'v'."""
    with pytest.raises(Exception):
        Manifest(
            component_id='test',
            component_type=ComponentType.SKILL,
            version='1.0.0',
            owner='owner',
            status=ComponentStatus.ACTIVE
        )
