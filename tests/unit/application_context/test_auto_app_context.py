import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_application_context_auto_config():
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

    # Создаем прикладной контекст БЕЗ конфигурации - должен автоматически создаться из реестра для prod
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=None,  # Не передаем конфигурацию - пусть создается автоматически
        profile='prod'
    )

    # Инициализируем прикладной контекст
    success = await app_context.initialize()
    print(f'ApplicationContext инициализирован: {success}')

    # Проверим, что у нас есть изолированные сервисы
    print(f'PromptService создан: {app_context._prompt_service is not None}')
    print(f'ContractService создан: {app_context._contract_service is not None}')

    # Проверим, что у нас есть изолированные инструменты
    print(f'Инструменты созданы: {len(app_context._tools)}')

    # Проверим, что конфигурация была создана автоматически
    print(f'AppConfig создан автоматически: {app_context.config is not None}')
    print(f'Профиль: {app_context.config.profile}')
    print(f'Prompt версии: {len(app_context.config.prompt_versions)}')

    # Проверим, что кэши изолированы
    ps1 = app_context._prompt_service
    print(f'PromptService кэш изолирован: {hasattr(ps1, "_cached_prompts")}')

    print('Тест автоматического создания конфигурации завершен успешно!')

# Запускаем тест
asyncio.run(test_application_context_auto_config())