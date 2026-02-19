"""Тесты модели Manifest с расширенной валидацией."""
import pytest
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus, QualityMetrics


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


def test_empty_owner_rejected():
    """Проверка отклонения пустого owner."""
    with pytest.raises(Exception):
        Manifest(
            component_id='test',
            component_type=ComponentType.SKILL,
            version='v1.0.0',
            owner='',
            status=ComponentStatus.ACTIVE
        )


def test_enum_values():
    """Проверка enum значений ComponentStatus."""
    assert ComponentStatus.ACTIVE.value == 'active'


def test_quality_metrics_range():
    """Проверка диапазона метрик качества."""
    with pytest.raises(Exception):
        QualityMetrics(success_rate_target=1.5)

    with pytest.raises(Exception):
        QualityMetrics(success_rate_target=-0.1)

    metrics = QualityMetrics(success_rate_target=0.95)
    assert metrics.success_rate_target == 0.95
