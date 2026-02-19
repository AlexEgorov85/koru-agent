"""Тесты FileSystemDataSource."""
import tempfile
from pathlib import Path
import pytest
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig


@pytest.fixture
def temp_dir():
    """Создание временной директории для тестов."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def registry_config():
    """Создание конфигурации реестра для тестов."""
    return RegistryConfig(profile='dev', capability_types={})


def test_filesystem_data_source_initialization(temp_dir, registry_config):
    """Проверка инициализации FileSystemDataSource."""
    ds = FileSystemDataSource(temp_dir, registry_config)
    ds.initialize()

    manifests_dir = temp_dir / 'manifests'
    assert manifests_dir.exists(), "Manifests directory should be created"


def test_filesystem_data_source_methods_exist(temp_dir, registry_config):
    """Проверка наличия методов работы с манифестами."""
    ds = FileSystemDataSource(temp_dir, registry_config)
    ds.initialize()

    assert hasattr(ds, 'load_manifest'), "FileSystemDataSource should have load_manifest method"
    assert hasattr(ds, 'list_manifests'), "FileSystemDataSource should have list_manifests method"
    assert hasattr(ds, 'manifest_exists'), "FileSystemDataSource should have manifest_exists method"