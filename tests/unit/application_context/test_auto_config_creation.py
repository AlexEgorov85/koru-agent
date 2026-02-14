import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_simple_context_creation():
    """Тест простого создания контекста без явной конфигурации"""
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

    # Создаем прикладной контекст БЕЗ передачи конфигурации - автоматическое создание
    print('\n1. Создание контекста для prod профиля без конфигурации...')
    app_context_prod = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='prod'
    )

    success = await app_context_prod.initialize()
    print(f'   ApplicationContext (prod) инициализирован: {success}')
    print(f'   AppConfig создан автоматически: {app_context_prod.config is not None}')
    print(f'   Профиль: {app_context_prod.config.profile}')

    # Создаем прикладной контекст для песочницы БЕЗ передачи конфигурации
    print('\n2. Создание контекста для sandbox профиля без конфигурации...')
    app_context_sandbox = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='sandbox'
    )

    success = await app_context_sandbox.initialize()
    print(f'   ApplicationContext (sandbox) инициализирован: {success}')
    print(f'   AppConfig создан автоматически: {app_context_sandbox.config is not None}')
    print(f'   Профиль: {app_context_sandbox.config.profile}')
    print(f'   Побочные эффекты в песочнице: {app_context_sandbox.config.side_effects_enabled}')

    # Проверим изоляцию между контекстами
    print('\n3. Проверка изоляции между контекстами...')
    if app_context_prod._prompt_service and app_context_sandbox._prompt_service:
        print(f'   PromptService изолированы: {app_context_prod._prompt_service is not app_context_sandbox._prompt_service}')
        print(f'   Кэши изолированы: {id(app_context_prod._prompt_service._cached_prompts) != id(app_context_sandbox._prompt_service._cached_prompts)}')
    else:
        print('   Один из сервисов не инициализирован')

    print('\nТест автоматического создания конфигурации завершен успешно!')

# Запускаем тест
asyncio.run(test_simple_context_creation())