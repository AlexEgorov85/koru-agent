"""Тесты MockDatabaseResourceDataSource."""
import pytest
from core.infrastructure.storage.mock_database_resource_data_source import MockDatabaseResourceDataSource
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus


@pytest.fixture
def data_source():
    """Создание и инициализация DataSource для тестов."""
    ds = MockDatabaseResourceDataSource()
    ds.initialize()
    yield ds


def test_manifest_creation():
    """Проверка создания манифеста."""
    manifest = Manifest(
        component_id='test_component',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='test_owner',
        status=ComponentStatus.ACTIVE
    )
    assert manifest.component_id == 'test_component'
    assert manifest.component_type == ComponentType.SKILL
    assert manifest.version == 'v1.0.0'


def test_manifest_add_and_load(data_source):
    """Проверка добавления и загрузки манифеста."""
    manifest = Manifest(
        component_id='test_component',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='test_owner',
        status=ComponentStatus.ACTIVE
    )

    data_source._manifests['skill.test_component'] = manifest
    loaded_manifest = data_source.load_manifest('skill', 'test_component')

    assert loaded_manifest is not None, "Manifest should be loaded"
    assert loaded_manifest.component_id == 'test_component'


def test_list_manifests(data_source):
    """Проверка списка манифестов."""
    manifest = Manifest(
        component_id='test_component',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='test_owner',
        status=ComponentStatus.ACTIVE
    )
    data_source._manifests['skill.test_component'] = manifest

    manifests = data_source.list_manifests()
    assert len(manifests) == 1, "Should have 1 manifest"


def test_manifest_exists(data_source):
    """Проверка существования манифеста."""
    manifest = Manifest(
        component_id='test_component',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='test_owner',
        status=ComponentStatus.ACTIVE
    )
    data_source._manifests['skill.test_component'] = manifest

    exists = data_source.manifest_exists('skill', 'test_component', 'v1.0.0')
    assert exists, "Manifest should exist"