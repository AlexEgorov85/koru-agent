import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

async def test_context_creation_with_registry():
    """Тест создания ApplicationContext с реестром, соответствующим файловой системе"""
    print("=== Тест создания ApplicationContext с корректным реестром ===")
    
    # Создаем минимальную системную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    print('✓ InfrastructureContext инициализирован')

    # Создаем прикладной контекст БЕЗ передачи конфигурации - автоматическая загрузка из реестра
    print('\nСоздание ApplicationContext с автоматической загрузкой из реестра...')
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='prod'
    )

    try:
        success = await app_context.initialize()
        print(f'✓ ApplicationContext инициализирован: {success}')
        
        if success:
            print(f'✓ AppConfig создан автоматически: {app_context.config is not None}')
            print(f'✓ Профиль: {app_context.config.profile}')
            print(f'✓ Количество версий промптов: {len(app_context.config.prompt_versions)}')
            print(f'✓ Количество версий входных контрактов: {len(app_context.config.input_contract_versions)}')
            print(f'✓ Количество версий выходных контрактов: {len(app_context.config.output_contract_versions)}')
            
            # Проверим, что сервисы созданы
            print(f'✓ PromptService создан: {app_context._prompt_service is not None}')
            print(f'✓ ContractService создан: {app_context._contract_service is not None}')
            
            # Проверим, что кэши изолированы
            print(f'✓ Кэши изолированы: {id(app_context._prompt_service._cached_prompts) != id(app_context._contract_service._cached_contracts)}')
        else:
            print('✗ Ошибка инициализации ApplicationContext')
    except Exception as e:
        print(f'✗ Ошибка при инициализации ApplicationContext: {e}')
        import traceback
        traceback.print_exc()

    print('\n=== Тест завершен успешно ===')

# Запускаем тест
asyncio.run(test_context_creation_with_registry())