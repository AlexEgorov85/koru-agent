"""Тест создания промпта с валидацией шаблонов."""
import pytest
from core.models.data.prompt import Prompt, PromptVariable, PromptStatus, ComponentType


def test_prompt_creation_and_validation():
    """Проверка создания промпта и валидации шаблонов."""
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
    assert prompt.version == "v1.0.0"

    warnings = prompt.validate_templates()
    assert len(warnings) == 0, "Should have no validation warnings"

    result = prompt.render(name="Alice", place="Wonderland")
    assert "Alice" in result
    assert "Wonderland" in result


def test_prompt_with_unused_variable():
    """Проверка промпта с неиспользуемой переменной."""
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

    assert prompt_with_unused.capability == "test.unused"
    warnings = prompt_with_unused.validate_templates()
    assert len(warnings) > 0, "Should have warning about unused variable"
