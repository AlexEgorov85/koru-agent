"""
Простой тест для проверки инициализации навыка
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor
from core.application.skills.planning.skill import PlanningSkill


async def test_simple():
    print("=== Простой тест инициализации ===")
    
    # Создаем минимальную конфигурацию
    component_config = ComponentConfig(
        variant_id="test_variant"
    )
    
    print("Конфигурация создана")
    
    # Создаем фейковый контекст приложения
    class FakeApplicationContext:
        def __init__(self):
            self.id = "test_context"
            self.logger = None
    
    fake_app_context = FakeApplicationContext()
    
    # Создаем фейковый ActionExecutor
    fake_executor = ActionExecutor(fake_app_context)
    
    # Создаем навык
    skill = PlanningSkill(
        name="test_planning_skill",
        application_context=fake_app_context,
        component_config=component_config,
        executor=fake_executor
    )
    
    print(f"Навык создан, _initialized = {skill._initialized}")
    
    # Инициализируем навык
    init_result = await skill.initialize()
    
    print(f"Результат инициализации: {init_result}")
    print(f"Флаг _initialized после инициализации: {skill._initialized}")
    
    # Проверим, что кэши остались пустыми, если нет ресурсов в конфигурации
    print(f"Кэш промптов: {skill._cached_prompts}")
    print(f"Кэш входных контрактов: {skill._cached_input_contracts}")
    print(f"Кэш выходных контрактов: {skill._cached_output_contracts}")


if __name__ == "__main__":
    asyncio.run(test_simple())