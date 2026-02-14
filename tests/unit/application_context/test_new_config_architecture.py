import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.context.agent_factory import AgentFactory
from core.config.app_config import AppConfig

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
    
    # Создаем фабрику агентов
    factory = AgentFactory(infra)
    print("+ AgentFactory создан")
    
    # Тестируем загрузку AppConfig из реестра
    app_config = AppConfig.from_registry(profile="prod")
    print(f"+ AppConfig загружен из реестра, профиль: {app_config.profile}")
    print(f"  - Промпты: {len(app_config.prompt_versions)} версий")
    print(f"  - Входные контракты: {len(app_config.input_contract_versions)} версий")
    print(f"  - Выходные контракты: {len(app_config.output_contract_versions)} версий")
    
    # Тестируем создание агента из реестра (новая архитектура)
    try:
        agent = await factory.create_agent_from_registry(
            goal="Тестовая цель",
        )
        print("+ Агент успешно создан с использованием новой архитектуры (из реестра)")
        print(f"  - ApplicationContext использует AppConfig из реестра")
        print(f"  - Количество версий промптов в контексте: {len(agent.system.config.prompt_versions)}")
    except Exception as e:
        print(f"! Ошибка при создании агента из реестра: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nТестирование завершено!")

# Запускаем тест
asyncio.run(test_new_architecture())