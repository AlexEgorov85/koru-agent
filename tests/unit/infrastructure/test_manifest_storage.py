import pytest
import tempfile
from pathlib import Path
import yaml
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.manifest import ComponentStatus


@pytest.fixture
def fs_data_source():
    with tempfile.TemporaryDirectory() as tmp_dir:
        registry_config = RegistryConfig(profile='dev', capability_types={})
        ds = FileSystemDataSource(Path(tmp_dir), registry_config)
        ds.initialize()
        yield ds


def test_list_manifests_empty(fs_data_source):
    manifests = fs_data_source.list_manifests()
    assert len(manifests) == 0


def test_load_manifest_not_found(fs_data_source):
    with pytest.raises(FileNotFoundError):
        fs_data_source.load_manifest('skill', 'nonexistent')


def test_manifest_exists(fs_data_source):
    # Создать тестовый манифест
    manifests_dir = fs_data_source.manifests_dir / "skills" / "test_skill"
    manifests_dir.mkdir(parents=True)
    
    manifest_data = {
        "component_id": "test_skill",
        "component_type": "skill",
        "version": "v1.0.0",
        "owner": "test_owner",
        "status": "active"
    }
    
    with open(manifests_dir / "manifest.yaml", 'w') as f:
        yaml.dump(manifest_data, f)
    
    # Перезагрузить для обновления кэша
    fs_data_source._loaded_manifests = {}
    fs_data_source._preload_manifests()
    
    assert fs_data_source.manifest_exists('skill', 'test_skill', 'v1.0.0')
    assert not fs_data_source.manifest_exists('skill', 'test_skill', 'v2.0.0')