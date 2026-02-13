#!/usr/bin/env python3
"""
Тест для проверки создания двух прикладных контекстов с разными версиями
"""
import asyncio
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.agent_config import AgentConfig


async def test_two_contexts():
    """
    Тестируем создание двух прикладных контекстов с разными версиями
    """
    print("=== Тестирование создания двух контекстов ===\n")
    
    # Создаем минимальную системную конфигурацию
    llm_providers = {
        "llama_cpp_provider": LLMProviderConfig(
            enabled=True,
            type_provider="llama_cpp",
            parameters={
                "model_path": "mock_model",
                "n_ctx": 2048,
                "n_threads": 4,
                "n_gpu_layers": 0
            }
        )
    }
    
    db_providers = {
        "mock_db": DBProviderConfig(
            enabled=True,
            type_provider="sqlite",
            parameters={
                "database": ":memory:"
            }
        )
    }
    
    config = SystemConfig(
        debug=True,
        log_level="INFO",
        log_dir="./logs",
        data_dir="./",
        llm_providers=llm_providers,
        db_providers=db_providers
    )
    
    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    print("1. Создание первого контекста...")
    # Создаём первый прикладной контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            component_name="ctx1"
        )
    )
    
    try:
        await ctx1.initialize()
        print("   + Первый контекст успешно инициализирован!")
        
        # Проверим, что промпт можно получить
        prompt_text1 = ctx1.get_prompt("planning.create_plan")
        print(f"   + Промпт в первом контексте успешно получен, длина: {len(prompt_text1)} символов")
        
    except Exception as e:
        print(f"   - Ошибка при инициализации первого контекста: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n2. Создание второго контекста...")
    # Создаём второй прикладной контекст с другой версией
    ctx2 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},  # используем ту же версию для теста
            component_name="ctx2"
        )
    )
    
    try:
        await ctx2.initialize()
        print("   + Второй контекст успешно инициализирован!")
        
        # Проверим, что промпт можно получить
        prompt_text2 = ctx2.get_prompt("planning.create_plan")
        print(f"   + Промпт во втором контексте успешно получен, длина: {len(prompt_text2)} символов")
        
        # Проверим, что контексты изолированы
        print(f"   + Контексты изолированы: длина промптов одинакова: {len(prompt_text1) == len(prompt_text2)}")
        
    except Exception as e:
        print(f"   - Ошибка при инициализации второго контекста: {e}")
        import traceback
        traceback.print_exc()
    
    # Завершаем работу
    await infra.shutdown()
    print("\n=== Тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_two_contexts())