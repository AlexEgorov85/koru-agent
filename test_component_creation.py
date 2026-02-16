import asyncio
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig

async def test_component_creation():
    # Используем директорию data/
    config = SystemConfig(data_dir='data')
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    # Создаем минимальную конфигурацию для тестирования
    app_config = AppConfig(config_id="test")
    
    # Добавим конфигурацию для prompt_service
    app_config.service_configs = {
        "prompt_service": ComponentConfig(
            variant_id="prompt_service_default",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )
    }
    
    app_context = ApplicationContext(infra, app_config, profile='prod')
    
    # Проверим, что компоненты разрешаются
    from core.application.context.application_context import ComponentType
    component_configs = app_context._resolve_component_configs()
    print(f"Resolved component configs: {list(component_configs.keys())}")
    
    prompt_service_config = component_configs[ComponentType.SERVICE].get("prompt_service")
    if prompt_service_config:
        print("Prompt service config found")
    else:
        print("Prompt service config NOT found")
    
    success = await app_context.initialize()
    
    print(f'Initialization success: {success}')
    
    # Проверим, что компонент зарегистрирован
    prompt_service = app_context.components.get(ComponentType.SERVICE, "prompt_service")
    if prompt_service:
        print(f"Prompt service registered: {prompt_service.name}")
    else:
        print("Prompt service NOT registered")
    
    await infra.shutdown()

asyncio.run(test_component_creation())