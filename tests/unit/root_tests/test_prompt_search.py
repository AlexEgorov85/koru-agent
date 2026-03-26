"""
Тест для проверки поиска промпта в системе
"""
import asyncio
from pathlib import Path

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext


async def test_prompt_search():
    """Тестирует поиск промпта в системе."""
    
    # Создаем минимальную системную конфигурацию
    llm_providers = {
        "mock_provider": LLMProviderConfig(
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
        log_level="DEBUG",
        log_dir="./logs",
        data_dir="./data",  # Правильный путь к данным
        llm_providers=llm_providers,
        db_providers=db_providers
    )

    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    
    # Проверяем, существует ли файл промпта
    expected_files = [
        Path("./data/prompts/skills/planning/create_plan_v1.0.0.yaml"),
        Path("./data/prompts/planning/create_plan/v1.0.0.yaml"),
        Path("./data/prompts/planning_create_plan_v1.0.0.yaml")
    ]
    
    for expected_file in expected_files:
    
    # Проверяем существование промпта через хранилище
    exists = await infra.prompt_storage.exists("planning.create_plan", "v1.0.0")
    
    # Попробуем загрузить промпт
    try:
        prompt = await infra.prompt_storage.load("planning.create_plan", "v1.0.0")
        if prompt:
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    await infra.shutdown()


if __name__ == "__main__":
    asyncio.run(test_prompt_search())