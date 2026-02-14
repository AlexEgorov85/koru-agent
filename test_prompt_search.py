"""
Тест для проверки поиска промпта в системе
"""
import asyncio
from pathlib import Path

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


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
    
    print("Инфраструктурный контекст инициализирован")
    print(f"Директория промптов: {infra.prompt_storage.prompts_dir}")
    
    # Проверяем, существует ли файл промпта
    expected_files = [
        Path("./data/prompts/skills/planning/create_plan_v1.0.0.yaml"),
        Path("./data/prompts/planning/create_plan/v1.0.0.yaml"),
        Path("./data/prompts/planning_create_plan_v1.0.0.yaml")
    ]
    
    print("\nПроверка существования файлов промпта:")
    for expected_file in expected_files:
        print(f"  {expected_file}: {'Существует' if expected_file.exists() else 'НЕ СУЩЕСТВУЕТ'}")
    
    # Проверяем существование промпта через хранилище
    print("\nПроверка существования через хранилище:")
    exists = await infra.prompt_storage.exists("planning.create_plan", "v1.0.0")
    print(f"Промпт planning.create_plan@v1.0.0 существует: {exists}")
    
    # Попробуем загрузить промпт
    print("\nПопытка загрузки промпта:")
    try:
        prompt = await infra.prompt_storage.load("planning.create_plan", "v1.0.0")
        print(f"Промпт успешно загружен: {prompt is not None}")
        if prompt:
            print(f"Статус промпта: {prompt.metadata.status if hasattr(prompt, 'metadata') and hasattr(prompt.metadata, 'status') else 'no status'}")
            print(f"Capability промпта: {prompt.metadata.capability if hasattr(prompt, 'metadata') and hasattr(prompt.metadata, 'capability') else 'no capability'}")
            print(f"Версия промпта: {prompt.metadata.version if hasattr(prompt, 'metadata') and hasattr(prompt.metadata, 'version') else 'no version'}")
    except Exception as e:
        print(f"Ошибка загрузки промпта: {e}")
        import traceback
        traceback.print_exc()
    
    await infra.shutdown()


if __name__ == "__main__":
    asyncio.run(test_prompt_search())