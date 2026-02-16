import asyncio
import tempfile
from pathlib import Path
import yaml
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.data.manifest import Manifest

async def test_manifest_loading():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Создаем структуру директорий для манифестов
        manifests_dir = Path(tmp_dir) / "manifests"
        (manifests_dir / "skills" / "test_skill").mkdir(parents=True)
        (manifests_dir / "services" / "test_service").mkdir(parents=True)
        (manifests_dir / "tools" / "test_tool").mkdir(parents=True)
        (manifests_dir / "behaviors" / "test_behavior").mkdir(parents=True)
        
        # Создаем тестовые манифесты
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
        
        # Создаем конфигурацию
        registry_config = RegistryConfig(profile='dev', capability_types={})
        
        # Создаем и инициализируем FileSystemDataSource
        ds = FileSystemDataSource(Path(tmp_dir), registry_config)
        ds.initialize()
        
        # Проверяем загрузку манифестов
        all_manifests = ds.list_manifests()
        print(f"Loaded {len(all_manifests)} manifests")
        
        # Проверяем загрузку конкретного манифеста
        test_manifest = ds.load_manifest('skill', 'test_skill')
        print(f"Loaded specific manifest: {test_manifest.component_id}")
        
        # Проверяем существование манифеста
        exists = ds.manifest_exists('skill', 'test_skill', 'v1.0.0')
        print(f"Manifest exists check: {exists}")
        
        print("[SUCCESS] All manifest functionality works correctly!")

asyncio.run(test_manifest_loading())