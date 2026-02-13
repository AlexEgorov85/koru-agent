#!/usr/bin/env python3
"""
Тестовый файл для проверки инициализации ApplicationContext
"""
import asyncio
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.agent_config import AgentConfig


async def test_application_context():
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
        data_dir="./",
        llm_providers=llm_providers,
        db_providers=db_providers
    )
    
    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    # Создаем конфигурацию агента с правильной версией промпта
    # Учитываем, что в YAML файле capability: "planning.create_plan"
    agent_config = AgentConfig(
        prompt_versions={"planning.create_plan": "v1.0.0"}
    )
    
    # Создаем и инициализируем прикладной контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=agent_config
    )
    
    try:
        await ctx1.initialize()
        print("ApplicationContext успешно инициализирован!")
        
        # Проверим, что промпт можно получить
        prompt_text = ctx1.get_prompt("planning.create_plan")
        print(f"Промпт успешно получен, длина: {len(prompt_text)} символов")
        
    except Exception as e:
        print(f"Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Завершаем работу
        await infra.shutdown()


if __name__ == "__main__":
    asyncio.run(test_application_context())