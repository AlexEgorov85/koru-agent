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
    print(f'   Профиль: {app_context_prod.config.profile if app_context_prod.config else "None"}')

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
    print(f'   Профиль: {app_context_sandbox.config.profile if app_context_sandbox.config else "None"}')
    print(f'   Побочные эффекты в песочнице: {app_context_sandbox.config.side_effects_enabled if app_context_sandbox.config else "None"}')

    # Проверим изоляцию между контекстами
    print('\n3. Проверка изоляции между контекстами...')
    prompt_service_prod = app_context_prod.get_service("prompt_service")
    prompt_service_sandbox = app_context_sandbox.get_service("prompt_service")
    if prompt_service_prod and prompt_service_sandbox:
        print(f'   PromptService изолированы: {prompt_service_prod is not prompt_service_sandbox}')
        print(f'   Кэши изолированы: {id(prompt_service_prod._cached_prompts) != id(prompt_service_sandbox._cached_prompts) if hasattr(prompt_service_prod, "_cached_prompts") and hasattr(prompt_service_sandbox, "_cached_prompts") else "Кэши недоступны"}')
    else:
        print('   Один из сервисов не инициализирован')

    print('\nТест автоматического создания конфигурации завершен успешно!')

# Запускаем тест
asyncio.run(test_simple_context_creation())