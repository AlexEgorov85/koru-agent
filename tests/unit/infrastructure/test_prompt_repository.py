import pytest
import tempfile
import os
from datetime import datetime
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, PromptUsageMetrics
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.repositories.in_memory_prompt_repository import InMemoryPromptRepository


@pytest.mark.asyncio
async def test_in_memory_prompt_repository_save_and_get():
    """Тест сохранения и получения версии промта в in-memory репозитории"""
    repo = InMemoryPromptRepository()
    
    version = PromptVersion(
        id="test_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Test prompt content",
        variables_schema=[
            {"name": "var1", "type": "string", "required": True, "description": "Variable 1"},
            {"name": "var2", "type": "string", "required": True, "description": "Variable 2"}
        ]
    )
    
    # Сохранение версии
    await repo.save_version(version)
    
    # Получение версии
    retrieved = await repo.get_version_by_id("test_version_123")
    
    assert retrieved is not None
    assert retrieved.id == "test_version_123"
    assert retrieved.content == "Test prompt content"
    assert [var.name for var in retrieved.variables_schema] == ["var1", "var2"]


@pytest.mark.asyncio
async def test_in_memory_prompt_repository_get_nonexistent():
    """Тест получения несуществующей версии"""
    repo = InMemoryPromptRepository()
    
    result = await repo.get_version_by_id("nonexistent_id")
    
    assert result is None


@pytest.mark.asyncio
async def test_in_memory_prompt_repository_get_active_version():
    """Тест получения активной версии по адресу"""
    repo = InMemoryPromptRepository()
    
    version = PromptVersion(
        id="test_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Test prompt content",
        status="active"
    )
    
    # Сохранение версии
    await repo.save_version(version)
    
    # Получение активной версии
    retrieved = await repo.get_active_version(
        domain="code_generation",
        capability_name="test_capability",
        provider_type="openai",
        role="system"
    )
    
    assert retrieved is not None
    assert retrieved.id == "test_version_123"
    assert retrieved.status == "active"


@pytest.mark.asyncio
async def test_in_memory_prompt_repository_activation():
    """Тест активации версии промта"""
    repo = InMemoryPromptRepository()
    
    version1 = PromptVersion(
        id="version_1",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="First version",
        status="active"
    )
    
    version2 = PromptVersion(
        id="version_2",
        semantic_version="1.1.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Second version",
        status="draft"
    )
    
    # Сохраняем обе версии
    await repo.save_version(version1)
    await repo.save_version(version2)
    
    # Проверяем, что первая активна
    active = await repo.get_active_version(
        domain="code_generation",
        capability_name="test_capability",
        provider_type="openai",
        role="system"
    )
    assert active.id == "version_1"
    
    # Активируем вторую версию
    await repo.activate_version("version_2")
    
    # Проверяем, что теперь активна вторая версия
    active = await repo.get_active_version(
        domain="code_generation",
        capability_name="test_capability",
        provider_type="openai",
        role="system"
    )
    assert active.id == "version_2"
    
    # Проверяем, что первая версия стала deprecated
    retrieved_v1 = await repo.get_version_by_id("version_1")
    assert retrieved_v1.status == "deprecated"


@pytest.mark.asyncio
async def test_in_memory_prompt_repository_update_metrics():
    """Тест обновления метрик использования"""
    repo = InMemoryPromptRepository()
    
    version = PromptVersion(
        id="test_version_123",
        semantic_version="1.0.0",
        domain=DomainType.CODE_GENERATION,
        provider_type=LLMProviderType.OPENAI,
        capability_name="test_capability",
        role=PromptRole.SYSTEM,
        content="Test prompt content"
    )
    
    # Сохраняем версию
    await repo.save_version(version)
    
    # Обновляем метрики
    metrics_update = PromptUsageMetrics(
        usage_count=5,
        success_count=4,
        avg_generation_time=1.2,
        last_used_at=datetime.utcnow(),
        error_rate=0.2
    )
    
    await repo.update_usage_metrics("test_version_123", metrics_update)
    
    # Получаем обновленную версию
    updated_version = await repo.get_version_by_id("test_version_123")
    
    assert updated_version.usage_metrics.usage_count == 5
    assert updated_version.usage_metrics.success_count == 4
    assert updated_version.usage_metrics.avg_generation_time == 1.2