"""
Тестирование обработки отсутствующих ресурсов в новой архитектуре
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.application.skills.planning.skill import PlanningSkill
from models.capability import Capability


async def test_missing_resources_handling():
    print("=== Тестирование обработки отсутствующих ресурсов ===")
    
    # Создаем конфигурацию с несуществующими ресурсами
    component_config = ComponentConfig(
        variant_id="test_variant",
        prompt_versions={"nonexistent.prompt": "v999"},  # несуществующий промпт
        input_contract_versions={"nonexistent.prompt": "v999"},  # несуществующий контракт
        output_contract_versions={"nonexistent.prompt": "v999"},  # несуществующий контракт
        resolved_prompts={},  # пустой словарь - ресурсы не найдены
        resolved_input_contracts={},
        resolved_output_contracts={}
    )
    
    print("[OK] Создана конфигурация с отсутствующими ресурсами")
    
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
    
    print("[OK] Навык создан с конфигурацией, содержащей отсутствующие ресурсы")
    
    # Инициализируем навык - должно пройти успешно
    init_result = await skill.initialize()
    assert init_result, "Инициализация должна пройти успешно даже с отсутствующими ресурсами"
    assert skill._initialized, "Флаг инициализации должен быть установлен"
    
    print("[OK] Навык успешно инициализирован с отсутствующими ресурсами")
    
    # Проверяем, что кэши остались пустыми (или содержат пустые значения)
    assert "nonexistent.prompt" in skill._cached_prompts, "Ключ должен быть в кэше даже если ресурс отсутствует"
    assert skill._cached_prompts["nonexistent.prompt"] == "", "Должно возвращаться пустое значение для отсутствующего промпта"
    
    print("[OK] Обработка отсутствующих промптов работает корректно")
    
    # Проверяем доступ к отсутствующему ресурсу - должно возвращать пустое значение, а не падать
    prompt = skill.get_prompt("nonexistent.prompt")
    assert prompt == "", "Доступ к отсутствующему промпту должен возвращать пустую строку"
    
    input_contract = skill.get_input_contract("nonexistent.prompt")
    assert input_contract == {}, "Доступ к отсутствующему входному контракту должен возвращать пустой словарь"
    
    output_contract = skill.get_output_contract("nonexistent.prompt")
    assert output_contract == {}, "Доступ к отсутствующему выходному контракту должен возвращать пустой словарь"
    
    print("[OK] Безопасный доступ к отсутствующим ресурсам работает корректно")
    
    print("\n=== Тест обработки отсутствующих ресурсов пройден успешно! ===")
    print("Новая архитектура корректно обрабатывает ситуации, когда ресурсы отсутствуют:")
    print("- Инициализация проходит успешно")
    print("- Отсутствующие ресурсы заменяются пустыми значениями")
    print("- Методы доступа к ресурсам не выбрасывают исключения")


if __name__ == "__main__":
    asyncio.run(test_missing_resources_handling())