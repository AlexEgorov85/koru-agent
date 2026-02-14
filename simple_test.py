import asyncio
import tempfile
import os
from pathlib import Path
import yaml

from core.config.models import SystemConfig, AgentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def test_profile_validation():
    """Test profile validation"""
    print("=== Testing prod/sandbox profiles ===")

    # Create temporary directory for data
    with tempfile.TemporaryDirectory() as temp_dir:
        # Prepare test data
        prompts_dir = Path(temp_dir) / "prompts"
        prompts_dir.mkdir(exist_ok=True)

        # Create test subdirectories and files
        planning_dir = prompts_dir / "planning"
        planning_dir.mkdir(exist_ok=True)

        # Create test YAML files with different statuses - structure should match what Prompt model expects
        test_prompts = {
            "v1.0.0": {
                "content": "Active prompt content",
                "version": "v1.0.0",
                "skill": "planning",
                "capability": "planning",
                "status": "active",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            },
            "v1.1.0": {
                "content": "Draft prompt content",
                "version": "v1.1.0",
                "skill": "planning",
                "capability": "planning",
                "status": "draft",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            },
            "v1.2.0": {
                "content": "Archived prompt content",
                "version": "v1.2.0",
                "skill": "planning",
                "capability": "planning",
                "status": "archived",
                "author": "test",
                "language": "ru",
                "tags": ["test"],
                "variables": [],
                "role": "system"
            }
        }

        for version, data in test_prompts.items():
            file_path = planning_dir / f"{version}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f)

        # Create configuration
        system_config = SystemConfig(data_dir=str(temp_dir))

        # Create infrastructure context
        infra = InfrastructureContext(system_config)
        await infra.initialize()

        print("Infrastructure context initialized")

        # Test production profile - should accept only active versions
        print("\n1. Testing production profile...")
        agent_config = AgentConfig(
            prompt_versions={"planning": "v1.0.0"}  # active version
        )

        try:
            prod_context = ApplicationContext(
                infrastructure_context=infra,
                config=agent_config,
                profile="prod"
            )
            success = await prod_context.initialize()
            print(f"   OK Production context with active version: {success}")
        except Exception as e:
            print(f"   ERROR Production context error: {e}")

        # Test production profile with draft version - should reject
        print("\n2. Testing production profile with draft version (should reject)...")
        agent_config_draft = AgentConfig(
            prompt_versions={"planning": "v1.1.0"}  # draft version
        )

        try:
            prod_context_draft = ApplicationContext(
                infrastructure_context=infra,
                config=agent_config_draft,
                profile="prod"
            )
            success = await prod_context_draft.initialize()
            print(f"   FAIL Production context with draft passed: {success} (ERROR!)")
        except Exception as e:
            print(f"   OK Production context with draft rejected: {type(e).__name__}")

        # Test sandbox with draft version - should accept
        print("\n3. Testing sandbox with draft version...")
        try:
            sandbox_context = ApplicationContext(
                infrastructure_context=infra,
                config=agent_config_draft,  # draft version
                profile="sandbox"
            )
            success = await sandbox_context.initialize()
            print(f"   OK Sandbox with draft version: {success}")
        except Exception as e:
            print(f"   ERROR Sandbox with draft version error: {e}")

        # Test sandbox with override
        print("\n4. Testing sandbox with override...")
        try:
            sandbox_context_override = ApplicationContext(
                infrastructure_context=infra,
                config=agent_config,  # active version
                profile="sandbox"
            )

            # Set override to draft version
            sandbox_context_override.set_prompt_override("planning", "v1.1.0")
            success = await sandbox_context_override.initialize()
            print(f"   OK Sandbox with override to draft version: {success}")
        except Exception as e:
            print(f"   ERROR Sandbox with override error: {e}")

        # Test override attempt in production - should raise error
        print("\n5. Testing override in production (should raise error)...")
        try:
            prod_context_for_override = ApplicationContext(
                infrastructure_context=infra,
                config=agent_config,
                profile="prod"
            )
            prod_context_for_override.set_prompt_override("planning", "v1.1.0")
            print("   FAIL Override in production passed (ERROR!)")
        except RuntimeError as e:
            print(f"   OK Override in production rejected: {e}")
        except Exception as e:
            print(f"   UNEXPECTED Error: {e}")

        # Shutdown infrastructure context
        await infra.shutdown()

        print("\n=== Profile testing completed ===")


if __name__ == "__main__":
    asyncio.run(test_profile_validation())