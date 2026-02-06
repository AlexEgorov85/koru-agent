"""
Фикстуры для capability
"""
from domain.models.capability import Capability


def create_test_capability(name: str = "test_capability", description: str = "Тест capability") -> Capability:
    """
    Создать тестовую capability
    """
    return Capability(
        name=name,
        description=description,
        skill_name="test_skill",
        parameters_schema={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Входные данные"}
            },
            "required": ["input"]
        }
    )


def create_capability_with_prompt_versions(name: str = "test_capability_with_prompts") -> Capability:
    """
    Создать тестовую capability с версиями промтов
    """
    return Capability(
        name=name,
        description="Тест capability с версиями промтов",
        skill_name="test_skill_with_prompts",
        prompt_versions={
            "openai:system": "test_system_prompt_version_id",
            "openai:user": "test_user_prompt_version_id"
        }
    )