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
    
    # Create minimal configuration
    config = SystemConfig()
    config.log_dir = temp_dir
    config.profile = "dev"
    config.log_level = "INFO"
    
    # Add minimal provider configurations
    config.llm_providers = {
        "test_llm": {
            "type_provider": "llama_cpp",
            "model_name": "tinyllama-1.1b",
            "parameters": {
                "n_ctx": 512,
                "n_threads": 1,
                "n_gpu_layers": -1
            },
            "enabled": True
        }
    }
    config.db_providers = {
        "test_db": {
            "type_provider": "postgres",
            "parameters": {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test",
                "password": "test"
            },
            "enabled": True
        }
    }
    
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
    
    # Shutdown
    await system_context.shutdown()
    print("\nSystem shut down successfully.")


if __name__ == "__main__":
    asyncio.run(test_component_registration())