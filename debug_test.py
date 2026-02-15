"""
Отладочный тест для проверки обработки отсутствующих ресурсов
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor
from core.application.skills.planning.skill import PlanningSkill


async def debug_test():
    print("=== Отладочный тест ===")
    
    # Создаем конфигурацию с несуществующими ресурсами
    component_config = ComponentConfig(
        variant_id="test_variant",
        prompt_versions={"nonexistent.prompt": "v999"},  # несуществующий промпт
        input_contract_versions={"nonexistent.prompt": "v999"},  # несуществующий контракт
        output_contract_versions={"nonexistent.prompt": "v999"},  # несуществующий контракт
    )
    
    print(f"prompt_versions: {component_config.prompt_versions}")
    print(f"input_contract_versions: {component_config.input_contract_versions}")
    print(f"output_contract_versions: {component_config.output_contract_versions}")
    
    # Создаем фейковый контекст приложения
    class FakeApplicationContext:
        def __init__(self):
            self.id = "test_context"
            import logging
            self.logger = logging.getLogger("test")
    
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
    
    # Проверим, какие ресурсы есть в конфигурации до инициализации
    print(f"resolved_prompts до инициализации: {skill.component_config.resolved_prompts}")
    print(f"resolved_input_contracts до инициализации: {skill.component_config.resolved_input_contracts}")
    print(f"resolved_output_contracts до инициализации: {skill.component_config.resolved_output_contracts}")
    
    # Инициализируем навык
    init_result = await skill.initialize()
    print(f"Результат инициализации: {init_result}")
    print(f"_initialized: {skill._initialized}")
    
    # Проверим, какие ресурсы попали в кэш
    print(f"_cached_prompts: {skill._cached_prompts}")
    print(f"_cached_input_contracts: {skill._cached_input_contracts}")
    print(f"_cached_output_contracts: {skill._cached_output_contracts}")


if __name__ == "__main__":
    asyncio.run(debug_test())