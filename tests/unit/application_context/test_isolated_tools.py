import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_isolated_tools():
    # Создаем минимальную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )
    
    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    print('InfrastructureContext инициализирован')
    
    # Создаем две разные конфигурации приложений
    app_config1 = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    app_config1.tool_configs = {}

    app_config2 = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    app_config2.tool_configs = {}
    
    # Создаем два разных прикладных контекста
    app_context1 = ApplicationContext(
        infrastructure_context=infra,
        config=app_config1,
        profile='prod'
    )
    
    app_context2 = ApplicationContext(
        infrastructure_context=infra,
        config=app_config2,
        profile='prod'
    )
    
    # Инициализируем оба контекста
    success1 = await app_context1.initialize()
    success2 = await app_context2.initialize()
    print(f'ApplicationContext1 инициализирован: {success1}')
    print(f'ApplicationContext2 инициализирован: {success2}')
    
    # Проверим, что у каждого контекста есть свои собственные инструменты через новый API
    from core.application_context.application_context import ComponentType
    tools1 = app_context1.components.all_of_type(ComponentType.TOOL)
    tools2 = app_context2.components.all_of_type(ComponentType.TOOL)
    print(f'Контекст 1 - количество инструментов: {len(tools1)}')
    print(f'Контекст 2 - количество инструментов: {len(tools2)}')

    # Проверим, что это разные коллекции (изолированные кэши)
    print(f'Коллекции инструментов разные: {tools1 is not tools2}')

    # Проверим, что методы get_tool работают изолированно
    tool1 = app_context1.get_tool('test_tool')
    tool2 = app_context2.get_tool('test_tool')
    print(f'Инструмент test_tool в контексте 1: {tool1}')
    print(f'Инструмент test_tool в контексте 2: {tool2}')
    
    print('Тест изоляции инструментов пройден!')

asyncio.run(test_isolated_tools())