import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_application_context_creation():
    # Создаем минимальную системную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    
    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    
    # Создаем AppConfig с минимальной конфигурацией
    app_config = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    
    # Создаем прикладной контекст с правильной конфигурацией
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    
    # Инициализируем прикладной контекст
    success = await app_context.initialize()
    
    # Проверим, что у нас есть изолированные сервисы через новый API
    prompt_service = app_context.get_service("prompt_service")
    contract_service = app_context.get_service("contract_service")

    # Проверим, что у нас есть изолированные инструменты через новый API
    from core.application_context.application_context import ComponentType
    tools = app_context.components.all_of_type(ComponentType.TOOL)

    # Проверим, что кэши изолированы
    

# Запускаем тест
asyncio.run(test_application_context_creation())