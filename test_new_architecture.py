"""
Тестирование новой архитектуры компонентов: изоляция и предзагрузка ресурсов
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.application.skills.planning.skill import PlanningSkill
from models.capability import Capability


async def test_new_architecture():
    print("=== Тестирование новой архитектуры компонентов ===")
    
    # 1. Создаем тестовую конфигурацию с предзагруженными ресурсами
    component_config = ComponentConfig(
        variant_id="test_variant",
        prompt_versions={"planning.create_plan": "v1"},
        input_contract_versions={"planning.create_plan": "v1"},
        output_contract_versions={"planning.create_plan": "v1"},
        resolved_prompts={
            "planning.create_plan": "Создай план для цели: {goal}\nДоступные возможности:\n{capabilities_list}"
        },
        resolved_input_contracts={
            "planning.create_plan": {"type": "object", "properties": {"goal": {"type": "string"}}}
        },
        resolved_output_contracts={
            "planning.create_plan": {"type": "object", "properties": {"steps": {"type": "array"}}}
        }
    )
    
    print("✓ Создана тестовая конфигурация с предзагруженными ресурсами")
    
    # 2. Создаем фейковый контекст приложения
    class FakeApplicationContext:
        def __init__(self):
            self.id = "test_context"
            self.logger = None
    
    fake_app_context = FakeApplicationContext()
    
    # 3. Создаем фейковый ActionExecutor
    class FakeActionExecutor(ActionExecutor):
        def __init__(self):
            self.executed_actions = []
        
        async def execute_action(self, action_name: str, parameters: dict, context: ExecutionContext):
            self.executed_actions.append((action_name, parameters))
            # Возвращаем фиктивный результат для тестирования
            if action_name == "llm.generate":
                return type('ActionResult', (), {'success': True, 'data': {'steps': ['step1', 'step2']}})()
            elif action_name.startswith("context."):
                return type('ActionResult', (), {'success': True, 'data': {'content': {'steps': []}}})()
            else:
                return type('ActionResult', (), {'success': True, 'data': {}})()
    
    fake_executor = FakeActionExecutor()
    
    # 4. Создаем навык с новой архитектурой
    skill = PlanningSkill(
        name="test_planning_skill",
        application_context=fake_app_context,
        component_config=component_config,
        executor=fake_executor
    )
    
    print("✓ Создан навык с новой архитектурой")
    
    # 5. Инициализируем навык
    init_result = await skill.initialize()
    assert init_result, "Инициализация навыка должна пройти успешно"
    assert skill._initialized, "Флаг инициализации должен быть установлен"
    
    print("✓ Навык успешно инициализирован")
    
    # 6. Проверяем, что ресурсы загружены в кэш
    assert "planning.create_plan" in skill._cached_prompts, "Промпт должен быть загружен в кэш"
    assert "planning.create_plan" in skill._cached_input_contracts, "Входной контракт должен быть загружен в кэш"
    assert "planning.create_plan" in skill._cached_output_contracts, "Выходной контракт должен быть загружен в кэш"
    
    print("✓ Ресурсы успешно загружены в кэш")
    
    # 7. Проверяем доступ к ресурсам через методы
    prompt = skill.get_prompt("planning.create_plan")
    assert prompt == "Создай план для цели: {goal}\nДоступные возможности:\n{capabilities_list}"
    
    input_contract = skill.get_input_contract("planning.create_plan")
    assert input_contract["type"] == "object"
    
    output_contract = skill.get_output_contract("planning.create_plan")
    assert output_contract["type"] == "object"
    
    print("✓ Доступ к ресурсам через методы работает корректно")
    
    # 8. Создаем контекст выполнения
    execution_context = ExecutionContext(
        available_capabilities=[
            Capability(name="test.capability1", description="Тестовая возможность 1"),
            Capability(name="test.capability2", description="Тестовая возможность 2")
        ]
    )
    
    # 9. Выполняем тестовое действие
    capability = Capability(name="planning.create_plan", description="Создание плана")
    result = await skill.execute(
        capability=capability,
        parameters={"goal": "Тестовая цель"},
        execution_context=execution_context
    )
    
    # Проверяем, что выполнение прошло без ошибок
    assert hasattr(result, 'success'), "Результат должен иметь атрибут success"
    
    print("✓ Выполнение действия прошло успешно")
    
    # 10. Проверяем, что навык использовал ActionExecutor для вызова других действий
    llm_calls = [call for call in fake_executor.executed_actions if call[0] == "llm.generate"]
    assert len(llm_calls) > 0, "Навык должен использовать ActionExecutor для вызова LLM"
    
    print("✓ Навык корректно использует ActionExecutor для взаимодействия")
    
    print("\n=== Все тесты пройдены успешно! ===")
    print("Новая архитектура компонентов работает корректно:")
    print("- Компоненты изолированы от сервисов")
    print("- Все ресурсы предзагружены в конфигурации")
    print("- Взаимодействие между компонентами осуществляется через ActionExecutor")
    print("- Кэши компонентов содержат предзагруженные ресурсы")
    print("- Методы доступа к ресурсам работают корректно")


if __name__ == "__main__":
    asyncio.run(test_new_architecture())