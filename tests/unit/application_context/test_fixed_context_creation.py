import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_context_creation_with_registry():
    """Тест создания ApplicationContext с реестром, соответствующим файловой системе"""
    
    # Создаем минимальную системную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()

    # Создаем прикладной контекст БЕЗ передачи конфигурации - автоматическая загрузка из реестра
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='prod'
    )

    try:
        success = await app_context.initialize()
        
        if success:
            
            # Проверим, что сервисы созданы
            
            # Проверим, что кэши изолированы
        else:
    except Exception as e:
        import traceback
        traceback.print_exc()


# Запускаем тест
asyncio.run(test_context_creation_with_registry())