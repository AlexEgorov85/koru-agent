import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_original_problem_fixed():
    """Тест, который раньше падал - теперь должен работать"""
    print("=== Тест решения оригинальной проблемы ===")
    
    # Создаем минимальную системную конфигурацию
    system_config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем инфраструктурный контекст
    infra = InfrastructureContext(system_config)
    await infra.initialize()
    print('+ InfrastructureContext инициализирован')

    # Создаем прикладной контекст ТАК, КАК РАНЬШЕ ПАДАЛО
    print('\nСоздание ApplicationContext как в оригинальной проблеме...')
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Это было причиной проблемы - не передавалась конфигурация
        profile='prod'
    )
    
    try:
        await ctx1.initialize()
        print('+ ApplicationContext успешно инициализирован!')
        print(f'  - Профиль: {ctx1.profile}')
        print(f'  - AppConfig создан автоматически: {ctx1.config is not None}')
        print(f'  - Количество версий промптов: {len(ctx1.config.prompt_versions)}')
        print(f'  - PromptService создан: {ctx1._prompt_service is not None}')
        print(f'  - ContractService создан: {ctx1._contract_service is not None}')
    except Exception as e:
        print(f'- Ошибка: {e}')
        import traceback
        traceback.print_exc()

    print('\n=== Тест оригинальной проблемы завершен ===')

# Запускаем тест
asyncio.run(test_original_problem_fixed())