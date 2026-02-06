"""
Фикстуры для промтов
"""
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptRole, VariableSchema
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


def create_test_prompt_version(
    content: str = "Тестовый промт с переменной {test_var}",
    status: PromptStatus = PromptStatus.ACTIVE,
    role: PromptRole = PromptRole.SYSTEM
) -> PromptVersion:
    """
    Создать тестовую версию промта
    """
    return PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=role,
        content=content,
        variables_schema=[
            VariableSchema(
                name="test_var",
                type="string",
                required=True,
                description="Тестовая переменная"
            )
        ],
        status=status
    )


def create_prompt_version_with_multiple_variables() -> PromptVersion:
    """
    Создать версию промта с несколькими переменными
    """
    return PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.USER,
        content="Промт с переменными: {required_var}, {optional_var}, {number_var}",
        variables_schema=[
            VariableSchema(
                name="required_var",
                type="string",
                required=True,
                description="Обязательная переменная"
            ),
            VariableSchema(
                name="optional_var",
                type="string",
                required=False,
                description="Опциональная переменная"
            ),
            VariableSchema(
                name="number_var",
                type="integer",
                required=True,
                description="Числовая переменная"
            )
        ],
        status=PromptStatus.ACTIVE
    )