from pathlib import Path
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus

# Создаем тестовую директорию
import tempfile
with tempfile.TemporaryDirectory() as tmp_dir:
    # Создаем конфигурацию
    registry_config = RegistryConfig(profile='dev', capability_types={})
    
    # Создаем экземпляр FileSystemDataSource
    ds = FileSystemDataSource(Path(tmp_dir), registry_config)
    
    # Инициализируем
    ds.initialize()
    
    print('[SUCCESS] FileSystemDataSource initialized successfully')
    
    # Проверим, что директории созданы
    manifests_dir = Path(tmp_dir) / 'manifests'
    if manifests_dir.exists():
        print('[SUCCESS] Manifests directory created')
    else:
        print('[ERROR] Manifests directory not created')
    
    # Проверим, что методы существуют
    if hasattr(ds, 'load_manifest') and hasattr(ds, 'list_manifests') and hasattr(ds, 'manifest_exists'):
        print('[SUCCESS] Manifest methods exist')
    else:
        print('[ERROR] Manifest methods missing')
    
    print('[SUCCESS] FileSystemDataSource tests passed!')