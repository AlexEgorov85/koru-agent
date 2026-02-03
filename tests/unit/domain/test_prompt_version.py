import pytest
from datetime import datetime
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, PromptUsageMetrics
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


def test_prompt_version_creation():
    """Тест создания версии промта"""
    from domain.models.prompt.prompt_version import VariableSchema
    
    version = PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="This is a test prompt",
        variables_schema=[
            VariableSchema(name="var1", type="string", required=True),
            VariableSchema(name="var2", type="string", required=True)
        ]
    )
    
    assert version.semantic_version == "1.0.0"
    assert version.domain == DomainType.CODE_GENERATION
    assert version.provider_type == LLMProviderType.OPENAI
    assert version.capability_name == "test_capability"
    assert version.role == PromptRole.SYSTEM
    assert version.content == "This is a test prompt"
    assert [var.name for var in version.variables_schema] == ["var1", "var2"]
    assert version.status == "draft"  # По умолчанию статус - draft, а не candidate
    assert version.usage_metrics is not None
    assert isinstance(version.created_at, datetime)


def test_prompt_version_get_address_key():
    """Тест получения адресного ключа"""
    version = PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="This is a test prompt"
    )
    
    expected_key = f"{DomainType.CODE_GENERATION.value}:{LLMProviderType.OPENAI.value}:test_capability:{PromptRole.SYSTEM.value}"
    assert version.get_address_key() == expected_key


def test_prompt_version_immutability():
    """Тест иммутабельности модели"""
    version = PromptVersion(
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="This is a test prompt"
    )
    
    # Попытка изменить атрибут должна вызвать ошибку
    with pytest.raises(Exception):
        version.content = "New content"


def test_prompt_usage_metrics_defaults():
    """Тест значений по умолчанию для метрик использования"""
    metrics = PromptUsageMetrics()
    
    assert metrics.usage_count == 0
    assert metrics.success_count == 0
    assert metrics.avg_generation_time == 0.0
    assert metrics.last_used_at is None
    assert metrics.error_rate == 0.0