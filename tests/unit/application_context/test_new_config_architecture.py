import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.agent.factory import AgentFactory  # Исправленный импорт
from core.config.app_config import AppConfig
from core.application.context.application_context import ApplicationContext

async def test_new_architecture():
    print("Тестирование новой архитектуры конфигурации...")

    # Создаем инфраструктурную конфигурацию
    config = SystemConfig(
        llm_providers={},
        db_providers={},
        data_dir='data'
    )

    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("+ InfrastructureContext инициализирован")

    # Создаем прикладной контекст (новая архитектура)
    app_config = AppConfig.from_registry(profile="prod")
    print(f"+ AppConfig загружен из реестра, профиль: {app_config.profile}")
    print(f"  - Промпты: {len(app_config.prompt_versions)} версий")
    print(f"  - Входные контракты: {len(app_config.input_contract_versions)} версий")
    print(f"  - Выходные контракты: {len(app_config.output_contract_versions)} версий")
    
    # Создаем ApplicationContext с компонентными конфигурациями
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod"
    )
    await app_context.initialize()
    print("+ ApplicationContext инициализирован")
    
    # Проверяем наличие service_configs, skill_configs, etc.
    print(f"  - Service configs: {list(getattr(app_config, 'service_configs', {}).keys())}")
    print(f"  - Skill configs: {list(getattr(app_config, 'skill_configs', {}).keys())}")
    print(f"  - Tool configs: {list(getattr(app_config, 'tool_configs', {}).keys())}")
    print(f"  - Behavior configs: {list(getattr(app_config, 'behavior_configs', {}).keys())}")

    # Создаем фабрику агентов (новая архитектура - использует ApplicationContext)
    factory = AgentFactory(app_context)  # Передаём ApplicationContext вместо InfrastructureContext
    print("+ AgentFactory создан")

    # Тестируем создание агента
    try:
        agent = await factory.create_agent(
            goal="Тестовая цель",
        )
        print("+ Агент успешно создан с использованием новой архитектуры")
        print(f"  - Агент использует ApplicationContext")
        print(f"  - Pattern ID: {agent.behavior_manager.get_current_pattern_id()}")
    except Exception as e:
        print(f"! Ошибка при создании агента: {e}")
        import traceback
        traceback.print_exc()

    print("\nТестирование завершено!")

# Запускаем тест
asyncio.run(test_new_architecture())