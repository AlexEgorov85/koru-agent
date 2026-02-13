# tests/diagnostic/test_prompt_cache_isolation.py
import asyncio
from core.application.context.application_context import ApplicationContext
from core.config.models import AgentConfig, SystemConfig  # Обновленный путь к конфигам
from core.infrastructure.context.infrastructure_context import InfrastructureContext


async def test_prompt_cache_isolation_bug():
    """
    Диагностический тест: проверяет, есть ли утечка кэша промптов.
    Если тест падает — критическая проблема изоляции.
    """
    # Создаём системную конфигурацию
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infrastructure_context = InfrastructureContext(config=system_config)
    await infrastructure_context.initialize()
    
    # Создаём 2 прикладных контекста с РАЗНЫМИ версиями
    config1 = AgentConfig(
        agent_id="test_agent_1",
        prompt_versions={"test.cap": "v1.0.0"}
    )
    ctx1 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config1
    )
    await ctx1.initialize()
    
    config2 = AgentConfig(
        agent_id="test_agent_2", 
        prompt_versions={"test.cap": "v2.0.0"}
    )
    ctx2 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config2
    )
    await ctx2.initialize()
    
    # Проверяем изоляцию кэшей
    prompt_service1 = ctx1.get_prompt_service()
    prompt_service2 = ctx2.get_prompt_service()
    
    # Проверяем, что это разные экземпляры
    print(f"PromptService1 ID: {id(prompt_service1)}")
    print(f"PromptService2 ID: {id(prompt_service2)}")
    print(f"Are they different instances? {prompt_service1 is not prompt_service2}")
    
    # Проверяем изоляцию кэшей - сравниваем внутренние кэши
    cache1_id = id(prompt_service1._prompt_objects)
    cache2_id = id(prompt_service2._prompt_objects)
    print(f"Cache1 ID: {cache1_id}")
    print(f"Cache2 ID: {cache2_id}")
    print(f"Are caches different? {cache1_id != cache2_id}")
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА ИЗОЛЯЦИИ:
    if cache1_id == cache2_id:
        print("ОШИБКА ИЗОЛЯЦИИ: оба контекста используют один и тот же кэш объектов промптов!")
        print("Нужно срочно проверить реализацию PromptService в приложении.")
        return False
    else:
        print("ОК: Кэши изолированы между контекстами")
        return True


if __name__ == "__main__":
    asyncio.run(test_prompt_cache_isolation_bug())