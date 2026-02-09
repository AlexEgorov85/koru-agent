#!/usr/bin/env python3
"""
Test script to verify that all components are properly registered after refactoring.
"""
import asyncio
import tempfile
import os
from core.config.models import SystemConfig
from core.system_context.system_context import SystemContext


async def test_component_registration_after_init():
    """Test that all components are properly registered during initialization."""
    print("Testing component registration during initialization...")
    
    # Create temporary directory for logs
    temp_dir = os.path.join(tempfile.gettempdir(), 'test_init_' + str(hash('test')))
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create minimal configuration without external dependencies
    config = SystemConfig()
    config.log_dir = temp_dir
    config.profile = "dev"
    config.log_level = "INFO"
    
    # Disable external providers to avoid connection issues
    config.llm_providers = {}
    config.db_providers = {}
    
    # Create system context
    system_context = SystemContext(config)
    
    # Initialize the system
    print("Initializing system context...")
    success = await system_context.initialize()
    print(f"Initialization success: {success}")
    
    # Check what's in the registry
    registry = system_context.registry
    print("\nRegistry contents after initialization:")
    print(f"Resources: {list(registry._resources.keys())}")
    print(f"Resources by type: {[(k, list(v)) for k, v in registry._by_type.items() if v]}")
    print(f"Capabilities count: {len(registry.list_capabilities())}")
    
    # Print capabilities if any
    capabilities = registry.list_capabilities()
    if capabilities:
        print("Capabilities:")
        for cap in capabilities:
            print(f"  - {cap.name}: {cap.description}")
    else:
        print("No capabilities registered.")
    
    # Check if prompt service was registered
    prompt_service = system_context.get_resource("prompt_service")
    if prompt_service:
        print("Prompt service registered successfully.")
    
    # Check specific tools and skills
    sql_tool = system_context.get_resource("SQLTool")
    book_skill = system_context.get_resource("BookLibrarySkill")
    
    if sql_tool:
        print("SQLTool registered successfully during initialization.")
    if book_skill:
        print("BookLibrarySkill registered successfully during initialization.")
    
    # Count total components
    total_resources = len(registry._resources)
    total_capabilities = len(registry.list_capabilities())
    print(f"\nTotal registered resources: {total_resources}")
    print(f"Total registered capabilities: {total_capabilities}")
    
    # Shutdown
    await system_context.shutdown()
    print("\nSystem shut down successfully.")


if __name__ == "__main__":
    asyncio.run(test_component_registration_after_init())