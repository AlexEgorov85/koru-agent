import asyncio
import tempfile
from pathlib import Path
import yaml
from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.models.manifest import ComponentStatus

async def test_application_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем структуру директорий и файлов
        data_dir = Path(temp_dir)
        
        # Создаем registry.yaml
        registry_data = {
            "profile": "dev",
            "active_prompts": {},
            "active_contracts": {},
            "services": {},
            "skills": {},
            "tools": {},
            "behaviors": {}
        }
        
        with open(data_dir / "registry.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(registry_data, f)
        
        # Создаем директорию для манифестов
        manifests_dir = data_dir / "manifests" / "skills" / "test_skill"
        manifests_dir.mkdir(parents=True)
        
        # Создаем тестовый манифест
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
        
        # Создаем конфигурацию системы
        config = SystemConfig(data_dir=str(data_dir))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        # Создаем конфигурацию приложения
        app_config = AppConfig(config_id="test")
        
        # Добавим конфигурацию для тестового навыка
        from core.config.component_config import ComponentConfig
        app_config.skill_configs = {
            "test_skill": ComponentConfig(
                variant_id="test_skill_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={},
                side_effects_enabled=True,
                detailed_metrics=False,
                parameters={},
                dependencies=[]
            )
        }
        
        # Создаем прикладной контекст
        app_context = ApplicationContext(infra, app_config, profile="dev")
        
        # Инициализируем
        success = await app_context.initialize()
        
        print(f'[SUCCESS] ApplicationContext initialized: {success}')
        
        if app_context.data_repository:
            print(f'[SUCCESS] Manifests loaded: {len(app_context.data_repository._manifest_cache)}')
            
            # Проверим получение манифеста
            manifest = app_context.data_repository.get_manifest('skill', 'test_skill')
            if manifest:
                print(f'[SUCCESS] Retrieved manifest: {manifest.component_id}@{manifest.version}')
            else:
                print('[ERROR] Could not retrieve manifest')
        
        await infra.shutdown()
        
        print('[SUCCESS] All ApplicationContext tests passed!')

# Запускаем тест
asyncio.run(test_application_context())