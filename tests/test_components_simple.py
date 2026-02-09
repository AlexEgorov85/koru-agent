#!/usr/bin/env python3
"""
Test script to verify that all components are properly registered after refactoring.
"""
import asyncio
import tempfile
import os
from core.config.models import SystemConfig
from core.system_context.system_context import SystemContext


async def test_component_registration():
    """Test that all components are properly registered."""
    print("Testing component registration after refactoring...")
    
    # Create temporary directory for logs
    temp_dir = os.path.join(tempfile.gettempdir(), 'test_components_' + str(hash('test')))
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
    print("\nRegistry contents:")
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
        print("No capabilities registered yet.")
    
    # Check if prompt service was registered
    prompt_service = system_context.get_resource("prompt_service")
    if prompt_service:
        print("Prompt service registered successfully.")
    
    # Check if tools and skills directories exist and try to register them
    print("\nChecking for tools and skills...")
    factory = system_context.provider_factory
    print("Discovering tools...")
    await factory.discover_and_create_all_tools()
    
    print("Discovering skills...")
    await factory.discover_and_create_all_skills()
    
    # Check registry again
    print(f"\nAfter discovery - Resources: {list(registry._resources.keys())}")
    print(f"After discovery - Resources by type: {[(k, list(v)) for k, v in registry._by_type.items() if v]}")
    print(f"After discovery - Capabilities count: {len(registry.list_capabilities())}")
    
    # Print any new capabilities
    capabilities = registry.list_capabilities()
    if capabilities:
        print("Capabilities after discovery:")
        for cap in capabilities:
            print(f"  - {cap.name}: {cap.description}")
    
    # Shutdown
    await system_context.shutdown()
    print("\nSystem shut down successfully.")


if __name__ == "__main__":
    asyncio.run(test_component_registration())