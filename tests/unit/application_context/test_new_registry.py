import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_app_context_with_new_registry():
    """Тестирование создания ApplicationContext с обновленным реестром"""
    print("Тестирование создания ApplicationContext с обновленным реестром...")
    
    # Создаем минимальную системную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    print('InfrastructureContext инициализирован')

    # Создаем прикладной контекст БЕЗ передачи конфигурации - автоматическое создание из реестра
    print('\nСоздание ApplicationContext с автоматической загрузкой из реестра...')
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='prod'
    )

    try:
        success = await app_context.initialize()
        print(f'ApplicationContext инициализирован: {success}')
        
        if success:
            print(f'AppConfig создан автоматически: {app_context.config is not None}')
            print(f'Профиль: {app_context.config.profile}')
            print(f'Количество версий промптов: {len(app_context.config.prompt_versions)}')
            print(f'Количество версий входных контрактов: {len(app_context.config.input_contract_versions)}')
            print(f'Количество версий выходных контрактов: {len(app_context.config.output_contract_versions)}')
            
            # Проверим, что сервисы созданы
            print(f'PromptService создан: {app_context._prompt_service is not None}')
            print(f'ContractService создан: {app_context._contract_service is not None}')
        else:
            print('Ошибка инициализации ApplicationContext')
    except Exception as e:
        print(f'Ошибка при инициализации ApplicationContext: {e}')
        import traceback
        traceback.print_exc()

    print('\nТест завершен!')

# Запускаем тест
asyncio.run(test_app_context_with_new_registry())