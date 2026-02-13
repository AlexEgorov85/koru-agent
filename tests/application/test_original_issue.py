#!/usr/bin/env python3
"""
Тестовый файл для проверки оригинального кода, который вызывал ошибки
"""
import asyncio
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.agent_config import AgentConfig


async def test_original_code():
    """
    Тестируем оригинальный код, который вызывал ошибки
    """
    print("=== Тестирование оригинального кода ===\n")
    
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
    
    # Оригинальный код, который вызывал ошибки
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            component_name="ctx1"
        )
    )
    
    try:
        await ctx1.initialize()
        print("+ ApplicationContext успешно инициализирован!")
        
        # Проверим, что промпт можно получить
        prompt_text = ctx1.get_prompt("planning.create_plan")
        print(f"+ Промпт успешно получен, длина: {len(prompt_text)} символов")
        
    except Exception as e:
        print(f"- Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
    
    # Завершаем работу
    await infra.shutdown()
    print("\n=== Тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_original_code())