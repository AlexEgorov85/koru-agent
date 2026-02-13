"""
Тестирование инфраструктурного контекста с обработкой ошибок установки llama-cpp-python
"""
import sys
import os
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext

async def test_infrastructure_with_error_handling():
    try:
        # Загрузка конфигурации
        config_loader = ConfigLoader()
        config = config_loader.load()
        
        print(f"Конфигурация загружена:")
        print(f"LLM провайдеры: {list(config.llm_providers.keys())}")
        print(f"DB провайдеры: {list(config.db_providers.keys())}")
        
        # Проверим параметры LLM провайдера
        for name, provider_config in config.llm_providers.items():
            print(f"  {name}: type={provider_config.type_provider}, enabled={provider_config.enabled}")
            print(f"    parameters: {provider_config.parameters}")
        
        # Создание инфраструктурного контекста
        infra = InfrastructureContext(config)
        
        print("\nИнициализация инфраструктурного контекста...")
        await infra.initialize()
        
        print("Инфраструктурный контекст успешно инициализирован!")
        print(f"Доступные ресурсы: {infra.resource_registry.get_all_names()}")
        
        # Проверка провайдеров
        for provider_name in infra.resource_registry.get_all_names():
            provider = infra.get_provider(provider_name)
            print(f"Провайдер '{provider_name}': {type(provider).__name__ if provider else 'None'}")
            
            # Попробуем выполнить health check для провайдера
            if hasattr(provider, 'health_check'):
                try:
                    health = await provider.health_check()
                    print(f"  Health status: {health.get('status', 'unknown')}")
                except Exception as e:
                    print(f"  Health check error: {e}")
        
        # Проверим DB провайдер отдельно
        db_provider = infra.get_provider('default_db')
        if db_provider:
            print(f"\nDB провайдер работает: {type(db_provider).__name__}")
            try:
                # Попробуем выполнить простой запрос
                result = await db_provider.execute("SELECT 1 as test;")
                print(f"Тестовый запрос к БД успешен: {result.rows}")
            except Exception as e:
                print(f"Ошибка при запросе к БД: {e}")
        
        # Завершение работы
        await infra.shutdown()
        print("\nИнфраструктурный контекст завершен")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_infrastructure_with_error_handling())