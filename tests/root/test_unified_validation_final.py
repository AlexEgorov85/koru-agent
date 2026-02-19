"""Тесты унифицированной системы валидации шаблонов."""
import pytest
from core.models.data.prompt import Prompt, PromptVariable, PromptStatus, ComponentType
from core.models.data.contract import Contract, ContractDirection
from core.models.data.manifest import Manifest, ComponentType as ManifestComponentType, ComponentStatus
from core.models.data.base_template_validator import TemplateValidatorMixin


def test_unified_template_validation_prompt():
    """Тест валидации шаблонов в Prompt."""
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

    assert prompt.capability == "test.capability"
    warnings = prompt.validate_templates()
    assert len(warnings) == 0, "Should have no validation warnings"

    result = prompt.render(name="Alice", place="Wonderland")
    assert "Alice" in result


def test_unused_variable_warning():
    """Тест предупреждения о неиспользуемой переменной."""
    prompt_with_unused = Prompt(
        capability="test.unused",
        version="v1.0.0",
        status=PromptStatus.ACTIVE,
        component_type=ComponentType.SKILL,
        content="Hello {name}! This is a test prompt with sufficient length.",
        variables=[
            PromptVariable(name="name", type="str", required=True, description="Name variable"),
            PromptVariable(name="unused_var", type="str", required=False, description="Unused variable")
        ]
    )

    warnings = prompt_with_unused.validate_templates()
    assert len(warnings) > 0, "Should have warning about unused variable"


def test_missing_variable_error():
    """Тест ошибки о недостающей переменной."""
    # Prompt валидирует обязательные переменные при создании
    # и выбрасывает ошибку если переменная в template отсутствует в variables
    with pytest.raises(Exception, match="place"):
        Prompt(
            capability="test.missing",
            version="v1.0.0",
            status=PromptStatus.ACTIVE,
            component_type=ComponentType.SKILL,
            content="Hello {name}, welcome to {place}! This is a test prompt.",
            variables=[
                PromptVariable(name="name", type="str", required=True, description="Name variable")
            ]
        )


def test_template_validator_mixin():
    """Тест TemplateValidatorMixin."""
    class TestComponent(TemplateValidatorMixin):
        def __init__(self, content, variables):
            self.content = content
            self.variables = variables

    component = TestComponent(
        content="Hello {name}!",
        variables=[PromptVariable(name="name", type="str", required=True, description="Name variable")]
    )

    warnings = component.validate_templates()
    assert len(warnings) == 0, "Should have no warnings for valid template"
