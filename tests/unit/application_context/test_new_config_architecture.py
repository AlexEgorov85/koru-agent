import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.agent.factory import AgentFactory  # Исправленный импорт
from core.config.app_config import AppConfig
from core.application_context.application_context import ApplicationContext

async def test_new_architecture():

    # Создаем инфраструктурную конфигурацию
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()

    # Создаем прикладной контекст (новая архитектура)
    app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
    
    # Создаем ApplicationContext с компонентными конфигурациями
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod"
    )
    await app_context.initialize()
    
    # Проверяем наличие service_configs, skill_configs, etc.

    # Создаем фабрику агентов (новая архитектура - использует ApplicationContext)
    factory = AgentFactory(app_context)  # Передаём ApplicationContext вместо InfrastructureContext

    # Тестируем создание агента
    try:
        agent = await factory.create_agent(
            goal="Тестовая цель",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()


# Запускаем тест
asyncio.run(test_new_architecture())