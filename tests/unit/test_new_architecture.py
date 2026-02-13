#!/usr/bin/env python3
"""Simple test script to verify the implementation."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.component_config import ComponentConfig
from core.application.context.application_context import ApplicationContext


async def test_basic_initialization():
    """Test basic initialization of the new architecture."""
    with TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        prompts_dir = data_dir / "prompts"
        prompts_dir.mkdir()

        # Create test capability directory
        test_cap_dir = prompts_dir / "test" / "capability"
        test_cap_dir.mkdir(parents=True)

        # Create test prompt files with proper structure
        prompt_v1_data = {
            "content": "Test prompt v1.0.0",
            "metadata": {
                "version": "v1.0.0",
                "skill": "test",
                "capability": "test.capability",
                "author": "test"
            }
        }
        import json
        (test_cap_dir / "v1.0.0.json").write_text(json.dumps(prompt_v1_data, ensure_ascii=False), encoding='utf-8')
        
        prompt_v2_data = {
            "content": "Test prompt v2.0.0",
            "metadata": {
                "version": "v2.0.0",
                "skill": "test",
                "capability": "test.capability",
                "author": "test"
            }
        }
        (test_cap_dir / "v2.0.0.json").write_text(json.dumps(prompt_v2_data, ensure_ascii=False), encoding='utf-8')

        # Infrastructure context
        infra_config = SystemConfig(
            data_dir=str(data_dir),
            llm_providers={},
            db_providers={}
        )
        infra = InfrastructureContext(infra_config)
        await infra.initialize()
        print("[OK] Infrastructure initialized successfully")

        # Application contexts with different configurations
        component_config1 = ComponentConfig(
            variant_id="ctx1",
            prompt_versions={"test.capability": "v1.0.0"},
            input_contract_versions={},
            output_contract_versions={}
        )
        ctx1 = ApplicationContext(
            infrastructure_context=infra,
            config=component_config1
        )
        await ctx1.initialize()
        print("[OK] ApplicationContext 1 initialized successfully")

        component_config2 = ComponentConfig(
            variant_id="ctx2",
            prompt_versions={"test.capability": "v2.0.0"},
            input_contract_versions={},
            output_contract_versions={}
        )
        ctx2 = ApplicationContext(
            infrastructure_context=infra,
            config=component_config2
        )
        await ctx2.initialize()
        print("[OK] ApplicationContext 2 initialized successfully")

        # Test getting prompts
        prompt1 = ctx1.get_prompt("test.capability")
        prompt2 = ctx2.get_prompt("test.capability")
        
        print(f"[OK] Prompt 1: {prompt1}")
        print(f"[OK] Prompt 2: {prompt2}")
        
        # Check isolation
        assert prompt1 != prompt2, "Prompts should be different"
        print("[OK] Prompts are isolated correctly")
        
        # Check cache isolation
        assert id(ctx1._prompt_service._cached_prompts) != id(ctx2._prompt_service._cached_prompts), \
            "Cache objects should be different"
        print("[OK] Cache objects are isolated correctly")
        
        print("\n[SUCCESS] All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_basic_initialization())