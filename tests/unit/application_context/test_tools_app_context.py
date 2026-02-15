import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_tools_in_app_context():
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
    
    # Создаем AppConfig с конфигурацией инструментов
    app_config = AppConfig(
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    # Добавим временно пустую конфигурацию инструментов
    app_config.tool_configs = {}
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    
    # Инициализируем прикладной контекст
    success = await app_context.initialize()
    print(f'ApplicationContext инициализирован: {success}')
    
    # Проверим, что у нас есть компоненты инструментов через новый API
    from core.application.context.application_context import ComponentType
    tools = app_context.components.all_of_type(ComponentType.TOOL)
    print(f'Количество инструментов: {len(tools)}')

    # Проверим метод get_tool (он теперь использует новый API)
    try:
        tool = app_context.get_tool('nonexistent_tool')
        print(f'Получение несуществующего инструмента: {tool}')
    except Exception as e:
        print(f'Ошибка при получении инструмента: {e}')
        import traceback
        traceback.print_exc()
    
    print('Тест завершен!')

asyncio.run(test_tools_in_app_context())