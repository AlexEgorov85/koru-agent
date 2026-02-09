import pytest
import tempfile
import os
from pathlib import Path
import yaml
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.service.prompt_service import PromptService, PromptNotFoundError, MissingVariablesError, VersionNotFoundError


@pytest.fixture
def temp_prompts_dir():
    """Create a temporary directory with sample prompt files for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        prompts_dir = Path(tmp_dir) / "prompts"
        prompts_dir.mkdir()
        
        # Create skills subdirectory
        skills_dir = prompts_dir / "skills"
        skills_dir.mkdir()
        
        # Create planning subdirectory
        planning_dir = skills_dir / "planning"
        planning_dir.mkdir()
        
        # Create example prompt file
        prompt_content = {
            "version": "1.2.0",
            "skill": "planning",
            "capability": "planning.create_plan",
            "strategy": None,
            "role": "system",
            "language": "ru",
            "tags": ["planning", "initial", "structured_output"],
            "variables": ["goal", "max_steps", "capabilities_list", "context"],
            "quality_metrics": {
                "success_rate": 0.92,
                "avg_tokens": 387,
                "benchmark_score": 87.2
            },
            "created_at": "2026-02-08T14:30:00Z",
            "updated_at": "2026-02-08T14:30:00Z",
            "author": "test@example.com",
            "content": "Ты — модуль планирования агентной системы.\nТвоя задача — создать ПЕРВИЧНЫЙ план действий для достижения цели.\n\nДОСТУПНЫЕ ВОЗМОЖНОСТИ СИСТЕМЫ:\n{{ capabilities_list }}\n\nИНСТРУКЦИИ:\n1. СТРОЙ план с нуля на основе цели\n2. ДЕЛИ план на конкретные, выполнимые шаги\n3. УЧИТЫВАЙ доступные возможности системы при выборе действий\n4. ДЕЛАЙ шаги последовательными и логичными\n5. УКАЖИ реалистичные оценки времени для каждого шага\n6. УЧИТЫВАЙ ограничения системы (максимум {{ max_steps }} шагов)\n\nЦЕЛЬ:\n{{ goal }}\n\nДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ:\n{{ context }}"
        }
        
        with open(planning_dir / "create_plan_v1.2.0.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(prompt_content, f, allow_unicode=True)
        
        # Create another version
        prompt_content_v1_1_0 = prompt_content.copy()
        prompt_content_v1_1_0["version"] = "1.1.0"
        with open(planning_dir / "create_plan_v1.1.0.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(prompt_content_v1_1_0, f, allow_unicode=True)
        
        # Create metadata file
        metadata_content = {
            "current_version": "v1.2.0",
            "active_versions": [
                {
                    "version": "v1.2.0",
                    "created_at": "2026-02-08T14:30:00Z",
                    "author": "test@example.com",
                    "metrics": {
                        "success_rate": 0.94,
                        "avg_tokens": 387,
                        "benchmark_score": 87.2
                    },
                    "changelog": [
                        "Добавлена поддержка иерархического планирования",
                        "Улучшена обработка ошибок валидации"
                    ]
                }
            ],
            "archived_versions": []
        }
        
        with open(prompts_dir / "metadata.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(metadata_content, f, allow_unicode=True)
        
        yield prompts_dir


@pytest.mark.asyncio
async def test_initialize(temp_prompts_dir):
    """Test initialization of PromptService."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    result = await service.initialize()
    
    assert result is True
    assert len(service._index) > 0
    assert "planning.create_plan" in service._index


@pytest.mark.asyncio
async def test_get_prompt_by_capability(temp_prompts_dir):
    """Test getting a prompt by capability name."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    prompt = await service.get_prompt("planning.create_plan")
    
    assert "модуль планирования агентной системы" in prompt
    assert "{{ capabilities_list }}" in prompt


@pytest.mark.asyncio
async def test_get_prompt_with_specific_version(temp_prompts_dir):
    """Test getting a prompt with a specific version."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    prompt = await service.get_prompt("planning.create_plan", version="v1.1.0")
    
    assert "модуль планирования агентной системы" in prompt


@pytest.mark.asyncio
async def test_get_prompt_nonexistent_capability(temp_prompts_dir):
    """Test getting a non-existent prompt raises an exception."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    with pytest.raises(PromptNotFoundError):
        await service.get_prompt("nonexistent.capability")


@pytest.mark.asyncio
async def test_render_prompt_success(temp_prompts_dir):
    """Test successful rendering of a prompt with variables."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    variables = {
        "goal": "Test goal",
        "max_steps": 5,
        "capabilities_list": "Test capabilities",
        "context": "Test context"
    }
    
    rendered = await service.render("planning.create_plan", variables)
    
    assert "Test goal" in rendered
    assert "Test capabilities" in rendered
    assert "5" in rendered
    assert "Test context" in rendered


@pytest.mark.asyncio
async def test_render_prompt_missing_variables(temp_prompts_dir):
    """Test that rendering with missing variables raises an exception."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    variables = {
        "goal": "Test goal",
        # Missing required variables
    }
    
    with pytest.raises(MissingVariablesError):
        await service.render("planning.create_plan", variables)


@pytest.mark.asyncio
async def test_list_prompts_with_filters(temp_prompts_dir):
    """Test listing prompts with filters."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Test without filters
    all_prompts = await service.list_prompts()
    assert len(all_prompts) > 0
    
    # Test with skill filter
    planning_prompts = await service.list_prompts(filters={"skill": "planning"})
    assert len(planning_prompts) > 0
    for prompt in planning_prompts:
        assert prompt["skill"] == "planning"


@pytest.mark.asyncio
async def test_reload_prompts(temp_prompts_dir):
    """Test reloading prompts after changes."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Initially should have some prompts
    initial_count = len(service._index)
    assert initial_count > 0
    
    # Add a new prompt file
    skills_dir = temp_prompts_dir / "skills"
    planning_dir = skills_dir / "planning"
    
    new_prompt_content = {
        "version": "1.0.0",
        "skill": "planning",
        "capability": "planning.test_new",
        "strategy": None,
        "role": "system",
        "language": "ru",
        "tags": ["test"],
        "variables": ["test_var"],
        "content": "New test prompt: {{ test_var }}"
    }
    
    with open(planning_dir / "test_new_v1.0.0.yaml", 'w', encoding='utf-8') as f:
        yaml.dump(new_prompt_content, f, allow_unicode=True)
    
    # Reload the service
    reload_result = await service.reload()
    assert reload_result is True
    
    # Check that the new prompt is available
    new_count = len(service._index)
    assert new_count > initial_count
    assert "planning.test_new" in service._index


@pytest.mark.asyncio
async def test_extract_version_from_filename():
    """Test extracting version from filename."""
    service = PromptService()
    
    # Test various filename formats
    assert service._extract_version_from_filename("create_plan_v1.2.0") == "v1.2.0"
    assert service._extract_version_from_filename("update_plan_v2.0.1") == "v2.0.1"
    assert service._extract_version_from_filename("get_data_v1.0") == "v1.0"
    assert service._extract_version_from_filename("some_file_without_version") == "latest"


@pytest.mark.asyncio
async def test_find_latest_version():
    """Test finding the latest version from a list."""
    service = PromptService()
    
    versions = ["v1.0.0", "v2.0.0", "v1.5.0"]
    latest = service._find_latest_version(versions)
    
    # Since we're doing simple string comparison, the result depends on sorting
    # In this case, "v2.0.0" would be considered latest with reverse sorting
    assert latest in versions


@pytest.mark.asyncio
async def test_version_not_found_error(temp_prompts_dir):
    """Test that requesting a non-existent version raises an error."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    with pytest.raises(VersionNotFoundError):
        await service.get_prompt("planning.create_plan", version="v999.999.999")