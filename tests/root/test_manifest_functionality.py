"""Тесты функциональности манифестов."""
import tempfile
from pathlib import Path
import yaml
import pytest
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig


@pytest.fixture
def temp_manifests_dir():
    """Создание временной директории с тестовыми манифестами."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifests_dir = tmp_path / "manifests"

        (manifests_dir / "skills" / "test_skill").mkdir(parents=True)
        (manifests_dir / "services" / "test_service").mkdir(parents=True)
        (manifests_dir / "tools" / "test_tool").mkdir(parents=True)
        (manifests_dir / "behaviors" / "test_behavior").mkdir(parents=True)

        test_manifests = [
            {
                "component_id": "test_skill",
                "component_type": "skill",
                "version": "v1.0.0",
                "owner": "test_owner",
                "status": "active",
                "dependencies": {"components": [], "tools": [], "services": []},
                "changelog": [{"version": "v1.0.0", "date": "2026-02-16", "author": "test", "changes": ["Initial release"]}]
            },
            {
                "component_id": "test_service",
                "component_type": "service",
                "version": "v1.0.0",
                "owner": "test_owner",
                "status": "active",
                "dependencies": {"components": [], "tools": [], "services": []},
                "changelog": [{"version": "v1.0.0", "date": "2026-02-16", "author": "test", "changes": ["Initial release"]}]
            },
            {
                "component_id": "test_tool",
                "component_type": "tool",
                "version": "v1.0.0",
                "owner": "test_owner",
                "status": "active",
                "dependencies": {"components": [], "tools": [], "services": []},
                "changelog": [{"version": "v1.0.0", "date": "2026-02-16", "author": "test", "changes": ["Initial release"]}]
            },
            {
                "component_id": "test_behavior",
                "component_type": "behavior",
                "version": "v1.0.0",
                "owner": "test_owner",
                "status": "active",
                "dependencies": {"components": [], "tools": [], "services": []},
                "changelog": [{"version": "v1.0.0", "date": "2026-02-16", "author": "test", "changes": ["Initial release"]}]
            }
        ]

        for manifest_data in test_manifests:
            component_type = manifest_data["component_type"]
            component_id = manifest_data["component_id"]
            manifest_path = manifests_dir / (component_type + "s") / component_id / "manifest.yaml"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest_data, f)

        yield tmp_path


@pytest.fixture
def data_source(temp_manifests_dir):
    """Создание FileSystemDataSource для тестов."""
    registry_config = RegistryConfig(profile='dev', capability_types={})
    ds = FileSystemDataSource(temp_manifests_dir, registry_config)
    ds.initialize()
    return ds


def test_list_manifests(data_source):
    """Проверка списка всех манифестов."""
    all_manifests = data_source.list_manifests()
    assert len(all_manifests) == 4, "Should load 4 manifests"


def test_load_specific_manifest(data_source):
    """Проверка загрузки конкретного манифеста."""
    test_manifest = data_source.load_manifest('skill', 'test_skill')
    assert test_manifest is not None
    assert test_manifest.component_id == 'test_skill'
    assert test_manifest.version == 'v1.0.0'


def test_manifest_exists(data_source):
    """Проверка существования манифеста."""
    exists = data_source.manifest_exists('skill', 'test_skill', 'v1.0.0')
    assert exists, "Manifest should exist"


def test_manifest_not_exists(data_source):
    """Проверка отсутствия манифеста."""
    exists = data_source.manifest_exists('skill', 'nonexistent', 'v1.0.0')
    assert not exists, "Nonexistent manifest should not exist"
