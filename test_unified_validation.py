from core.models.prompt import Prompt, PromptVariable, PromptStatus, ComponentType

# Тест создания промпта
try:
    prompt = Prompt(
        capability="test.capability",
        version="v1.0.0",
        status=PromptStatus.ACTIVE,
        component_type=ComponentType.SKILL,
        content="Hello {name}, welcome to {place}! This is a test prompt with sufficient length.",
        variables=[
            PromptVariable(name="name", type="str", required=True, description="Name variable"),
            PromptVariable(name="place", type="str", required=True, description="Place variable")
        ]
    )
    
    print(f"✓ Промпт создан успешно: {prompt.capability}@{prompt.version}")
    
    # Проверим валидацию шаблонов
    warnings = prompt.validate_templates()
    print(f"✓ Валидация шаблонов выполнена, предупреждений: {len(warnings)}")
    
    # Проверим рендеринг
    result = prompt.render(name="Alice", place="Wonderland")
    print(f"✓ Рендеринг успешен: {result}")
    
except Exception as e:
    print(f"[ERROR] Ошибка: {e}")

# Тест с неиспользуемой переменной
try:
    prompt_with_unused = Prompt(
        capability="test.unused",
        version="v1.0.0",
        status=PromptStatus.ACTIVE,
        component_type=ComponentType.SKILL,
        content="Hello {name}! This is a test prompt with sufficient length.",
        variables=[
            PromptVariable(name="name", type="str", required=True, description="Name variable"),
            PromptVariable(name="unused_var", type="str", required=False, description="Unused variable")  # Не используется в шаблоне
        ]
    )
    
    print(f"✓ Промпт с неиспользуемой переменной создан: {prompt_with_unused.capability}@{prompt_with_unused.version}")
    
except Exception as e:
    print(f"[ERROR] Ошибка с неиспользуемой переменной: {e}")