#!/usr/bin/env python3
"""
Пример правильного использования ApplicationContext
"""
import asyncio
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def demo_correct_usage():
    """
    Демонстрация правильного использования ApplicationContext
    """
    print("=== Демонстрация правильного использования ApplicationContext ===\n")
    
    # 1. Создаем минимальную системную конфигурацию
    print("1. Создание системной конфигурации...")
    llm_providers = {
        "llama_cpp_provider": LLMProviderConfig(
            enabled=True,
            type_provider="llama_cpp",
            parameters={
                "model_path": "mock_model",  # используем mock модель для тестирования
                "n_ctx": 2048,
                "n_threads": 4,
                "n_gpu_layers": 0
            }
        )
    }
    
    db_providers = {
        "mock_db": DBProviderConfig(
            enabled=True,
            type_provider="sqlite",  # используем sqlite вместо postgres
            parameters={
                "database": ":memory:"  # используем in-memory базу данных
            }
        )
    }
    
    config = SystemConfig(
        debug=True,
        log_level="INFO",
        log_dir="./logs",
        data_dir="./data",
        llm_providers=llm_providers,
        db_providers=db_providers
    )
    
    # 2. Создаем и инициализируем инфраструктурный контекст
    print("2. Инициализация инфраструктурного контекста...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("   Инфраструктурный контекст успешно инициализирован\n")
    
    # 3. Создаем конфигурацию приложения с правильной версией промпта
    print("3. Создание конфигурации приложения...")
    # Учитываем, что в YAML файле capability: "planning.create_plan"
    from core.config.app_config import AppConfig
    app_config = AppConfig(
        prompt_versions={"planning.create_plan": "v1.0.0"},
        side_effects_enabled=True,
        detailed_metrics=False
    )
    print(f"   Конфигурация приложения создана с промптом: {list(app_config.prompt_versions.keys())[0]}@{list(app_config.prompt_versions.values())[0]}\n")
    
    # 4. Создаем и инициализируем прикладной контекст
    print("4. Инициализация прикладного контекста...")
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=None  # Теперь может быть None для продакшена
    )
    
    try:
        await ctx1.initialize()
        print("   ApplicationContext успешно инициализирован!\n")
        
        # 5. Проверим, что промпт можно получить
        print("5. Проверка получения промпта...")
        prompt_text = ctx1.get_prompt("planning.create_plan")
        print(f"   Промпт успешно получен, длина: {len(prompt_text)} символов")
        print(f"   Первые 100 символов промпта: {prompt_text[:100]}...\n")
        
        print("=== Демонстрация завершена успешно! ===")
        
    except Exception as e:
        print(f"   Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Завершаем работу
    print("\n6. Завершение работы...")
    await infra.shutdown()
    print("   Работа успешно завершена")


if __name__ == "__main__":
    asyncio.run(demo_correct_usage())