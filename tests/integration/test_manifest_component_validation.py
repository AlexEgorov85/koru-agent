import pytest
import asyncio
from pathlib import Path
import tempfile
import yaml

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.mark.asyncio
async def test_component_validates_manifest_on_init():
    """Тест: компонент валидирует манифест при инициализации."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаём манифест со статусом draft для prod
        manifests_dir = Path(temp_dir) / "manifests" / "skills" / "test_skill"
        manifests_dir.mkdir(parents=True)
        
        manifest_data = {
            "component_id": "test_skill",
            "component_type": "skill",
            "version": "v1.0.0",
            "owner": "test_owner",
            "status": "draft"  # Draft для prod
        }
        
        with open(manifests_dir / "manifest.yaml", 'w') as f:
            yaml.dump(manifest_data, f)
        
        config = SystemConfig(data_dir=temp_dir)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig(config_id="test")
        app_context = ApplicationContext(infra, app_config, profile="prod")
        
        success = await app_context.initialize()
        
        # В prod должно быть отклонено
        assert success == False, "Prod должен отклонить draft статус"
        
        await infra.shutdown()


@pytest.mark.asyncio
async def test_component_validates_resources_on_init():
    """Тест: компонент валидирует загруженные ресурсы."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаём манифест с active статусом
        manifests_dir = Path(temp_dir) / "manifests" / "skills" / "test_skill"
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
        
        config = SystemConfig(data_dir=temp_dir)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig(config_id="test")
        app_context = ApplicationContext(infra, app_config, profile="prod")
        
        success = await app_context.initialize()
        
        # В prod должно быть принято
        assert success == True, "Prod должен принять active статус"
        
        await infra.shutdown()


@pytest.mark.asyncio
async def test_no_duplicate_versions_validation():
    """Тест: валидация отсутствия дублирования версий."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = SystemConfig(data_dir=temp_dir)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig(config_id="test")
        app_context = ApplicationContext(infra, app_config, profile="prod")
        await app_context.initialize()
        
        from core.application.services.manifest_validation_service import ManifestValidationService
        
        validation_service = ManifestValidationService(app_context.data_repository)
        report = await validation_service.validate_no_duplicates()
        
        # В пустой системе не должно быть дубликатов
        assert report['is_valid'] == True
        
        await infra.shutdown()