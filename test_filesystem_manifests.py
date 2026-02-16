from pathlib import Path
import yaml
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.manifest import Manifest, ComponentType, ComponentStatus

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
    
    # Создадим тестовый манифест
    manifests_dir = Path(tmp_dir) / 'manifests' / 'skills' / 'test_skill'
    manifests_dir.mkdir(parents=True)
    
    manifest_data = {
        "component_id": "test_skill",
        "component_type": "skill",
        "version": "v1.0.0",
        "owner": "test_owner",
        "status": "active",
        "dependencies": {
            "components": [],
            "tools": [],
            "services": []
        },
        "changelog": []
    }
    
    with open(manifests_dir / "manifest.yaml", 'w', encoding='utf-8') as f:
        yaml.dump(manifest_data, f)
    
    # Перезагрузим DataSource, чтобы он прочитал новый манифест
    ds = FileSystemDataSource(Path(tmp_dir), registry_config)
    ds.initialize()
    
    # Проверим загрузку манифеста
    try:
        manifest = ds.load_manifest('skill', 'test_skill')
        print(f'[SUCCESS] Manifest loaded: {manifest.component_id}@{manifest.version}')
    except Exception as e:
        print(f'[ERROR] Failed to load manifest: {e}')
    
    # Проверим список манифестов
    manifests = ds.list_manifests()
    print(f'[SUCCESS] Found {len(manifests)} manifests')
    
    # Проверим существование манифеста
    exists = ds.manifest_exists('skill', 'test_skill', 'v1.0.0')
    print(f'[SUCCESS] Manifest exists: {exists}')
    
    print('[SUCCESS] All FileSystemDataSource manifest tests passed!')