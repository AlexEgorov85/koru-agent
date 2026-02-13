"""
Тестирование инфраструктурного контекста с реальными параметрами
"""
import sys
import os
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext

async def test_infrastructure():
    try:
        # Загрузка конфигурации
        config_loader = ConfigLoader()
        config = config_loader.load()
        
        print(f"Конфигурация загружена:")
        print(f"LLM провайдеры: {list(config.llm_providers.keys())}")
        print(f"DB провайдеры: {list(config.db_providers.keys())}")
        
        # Создание инфраструктурного контекста
        infra = InfrastructureContext(config)
        
        print("Инициализация инфраструктурного контекста...")
        await infra.initialize()
        
        print("Инфраструктурный контекст успешно инициализирован!")
        print(f"Доступные ресурсы: {infra.resource_registry.get_all_names()}")
        
        # Проверка провайдеров
        for provider_name in infra.resource_registry.get_all_names():
            provider = infra.get_provider(provider_name)
            print(f"Провайдер '{provider_name}': {type(provider).__name__ if provider else 'None'}")
        
        # Завершение работы
        await infra.shutdown()
        print("Инфраструктурный контекст завершен")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_infrastructure())