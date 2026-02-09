import pytest
import tempfile
import os
from pathlib import Path
import yaml
from unittest.mock import AsyncMock, MagicMock

from core.infrastructure.service.prompt_service import PromptService
from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig


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
        prompt_content_v1_1_0["capability"] = "planning.update_plan"
        with open(planning_dir / "update_plan_v1.1.0.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(prompt_content_v1_1_0, f, allow_unicode=True)
        
        # Create a book library prompt
        book_prompt_content = {
            "version": "1.0.0",
            "skill": "book_library",
            "capability": "book_library.search_books",
            "strategy": None,
            "role": "system",
            "language": "ru",
            "tags": ["book_library", "search"],
            "variables": ["query", "author", "genre"],
            "content": "Ты — модуль поиска книг.\nПоищи книги по запросу: {{ query }}, автору: {{ author }}, жанру: {{ genre }}"
        }
        
        book_lib_dir = skills_dir / "book_library"
        book_lib_dir.mkdir()
        with open(book_lib_dir / "search_books_v1.0.0.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(book_prompt_content, f, allow_unicode=True)
        
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
async def test_prompt_service_integration_with_system_context(temp_prompts_dir):
    """Test that PromptService integrates correctly with SystemContext."""
    # Create a minimal config with prompts directory
    config = SystemConfig()
    config.prompts_dir = str(temp_prompts_dir)
    
    # Create system context
    system_context = SystemContext(config=config)
    
    # Initialize the system
    success = await system_context.initialize()
    assert success is True
    
    # Get the prompt service from the system context
    prompt_service = system_context.get_resource("prompt_service")
    assert prompt_service is not None
    assert isinstance(prompt_service, PromptService)
    
    # Test that the service was properly initialized
    assert len(prompt_service._index) > 0
    assert "planning.create_plan" in prompt_service._index


@pytest.mark.asyncio
async def test_prompt_service_end_to_end_workflow(temp_prompts_dir):
    """Test end-to-end workflow with PromptService."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Test that we can get a prompt
    prompt = await service.get_prompt("planning.create_plan")
    assert "модуль планирования агентной системы" in prompt
    
    # Test that we can render the prompt with variables
    variables = {
        "goal": "Build a house",
        "max_steps": 10,
        "capabilities_list": "build, design, purchase materials",
        "context": "Construction project"
    }
    
    rendered_prompt = await service.render("planning.create_plan", variables)
    assert "Build a house" in rendered_prompt
    assert "10" in rendered_prompt
    assert "build, design, purchase materials" in rendered_prompt
    assert "Construction project" in rendered_prompt


@pytest.mark.asyncio
async def test_prompt_service_hot_reload_integration(temp_prompts_dir):
    """Test hot reload functionality in integration context."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Count initial prompts
    initial_prompts = await service.list_prompts()
    initial_count = len(initial_prompts)
    
    # Add a new prompt file to the directory
    skills_dir = temp_prompts_dir / "skills"
    planning_dir = skills_dir / "planning"
    
    new_prompt_content = {
        "version": "1.0.0",
        "skill": "planning",
        "capability": "planning.finalize_plan",
        "strategy": None,
        "role": "system",
        "language": "ru",
        "tags": ["planning", "final"],
        "variables": ["plan", "results"],
        "content": "Ты — модуль финализации плана.\nФинализируй план: {{ plan }} с результатами: {{ results }}"
    }
    
    with open(planning_dir / "finalize_plan_v1.0.0.yaml", 'w', encoding='utf-8') as f:
        yaml.dump(new_prompt_content, f, allow_unicode=True)
    
    # Reload the service
    reload_success = await service.reload()
    assert reload_success is True
    
    # Check that the new prompt is now available
    updated_prompts = await service.list_prompts()
    updated_count = len(updated_prompts)
    
    assert updated_count == initial_count + 1
    assert any(p['capability'] == 'planning.finalize_plan' for p in updated_prompts)
    
    # Test that the new prompt can be retrieved and rendered
    new_prompt = await service.get_prompt("planning.finalize_plan")
    assert "модуль финализации плана" in new_prompt
    
    rendered_new = await service.render("planning.finalize_plan", {
        "plan": "Sample plan",
        "results": "Sample results"
    })
    assert "Sample plan" in rendered_new
    assert "Sample results" in rendered_new


@pytest.mark.asyncio
async def test_prompt_service_with_different_strategies(temp_prompts_dir):
    """Test prompt service with different strategies."""
    # Add a strategy-specific prompt
    strategies_dir = temp_prompts_dir / "strategies"
    strategies_dir.mkdir(exist_ok=True)
    
    react_dir = strategies_dir / "react"
    react_dir.mkdir(exist_ok=True)
    
    strategy_prompt_content = {
        "version": "1.3.0",
        "skill": "reasoning",
        "capability": "strategies.react.reasoning",
        "strategy": "react",
        "role": "system",
        "language": "ru",
        "tags": ["reasoning", "react", "thought_process"],
        "variables": ["input_query", "context", "available_tools"],
        "content": "Ты — модуль рассуждения стратегии ReAct.\nРассуждай по поводу: {{ input_query }} в контексте: {{ context }}"
    }
    
    with open(react_dir / "reasoning_v1.3.0.yaml", 'w', encoding='utf-8') as f:
        yaml.dump(strategy_prompt_content, f, allow_unicode=True)
    
    # Test with the service
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Test getting strategy-specific prompt
    prompt = await service.get_prompt("strategies.react.reasoning", strategy="react")
    assert "модуль рассуждения стратегии ReAct" in prompt
    
    # Test rendering with variables
    rendered = await service.render(
        "strategies.react.reasoning",
        {
            "input_query": "Calculate 2+2",
            "context": "Mathematical calculation",
            "available_tools": "Calculator"
        },
        strategy="react"
    )
    assert "Calculate 2+2" in rendered
    assert "Mathematical calculation" in rendered


@pytest.mark.asyncio
async def test_prompt_service_version_resolution(temp_prompts_dir):
    """Test version resolution functionality."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Test getting prompt with default version (should use metadata.yaml current_version)
    prompt_default = await service.get_prompt("planning.create_plan")
    # This should get the current version from metadata (v1.2.0)
    
    # Test getting prompt with explicit version
    prompt_v1_2_0 = await service.get_prompt("planning.create_plan", version="v1.2.0")
    prompt_v1_1_0 = await service.get_prompt("planning.create_plan", version="v1.1.0")
    
    # Both explicit versions should work
    assert "модуль планирования агентной системы" in prompt_v1_2_0
    assert "модуль планирования агентной системы" in prompt_v1_1_0
    
    # Default and explicit v1.2.0 should be the same
    assert prompt_default == prompt_v1_2_0


@pytest.mark.asyncio
async def test_prompt_service_validation_features(temp_prompts_dir):
    """Test validation features of the prompt service."""
    service = PromptService(prompts_dir=str(temp_prompts_dir))
    await service.initialize()
    
    # Test with missing required variables
    incomplete_vars = {
        "goal": "Test goal",
        # Missing other required vars
    }
    
    with pytest.raises(Exception):  # Should raise MissingVariablesError
        await service.render("planning.create_plan", incomplete_vars)
    
    # Test with all required variables (should work)
    complete_vars = {
        "goal": "Test goal",
        "max_steps": 5,
        "capabilities_list": "Test capabilities",
        "context": "Test context"
    }
    
    rendered = await service.render("planning.create_plan", complete_vars)
    assert "Test goal" in rendered
    assert "Test capabilities" in rendered