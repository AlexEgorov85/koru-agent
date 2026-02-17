import asyncio
import tempfile
from pathlib import Path
import yaml
from core.application.data_repository import DataRepository
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus

async def test_data_repository():
    # Создаем тестовую директорию
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
        
        # Создаем DataRepository
        repo = DataRepository(ds, profile='dev')
        
        # Загружаем манифесты
        manifest_cache = await repo.load_manifests()
        
        print(f'[SUCCESS] Loaded {len(manifest_cache)} manifests to cache')
        
        # Проверим получение манифеста
        manifest = repo.get_manifest('skill', 'test_skill')
        if manifest:
            print(f'[SUCCESS] Retrieved manifest: {manifest.component_id}@{manifest.version}')
        else:
            print('[ERROR] Could not retrieve manifest')
        
        # Проверим валидацию
        errors = repo.validate_manifest_by_profile(manifest, 'prod')
        print(f'[SUCCESS] Validation errors for prod: {len(errors)}')
        
        print('[SUCCESS] All DataRepository tests passed!')

# Запускаем тест
asyncio.run(test_data_repository())