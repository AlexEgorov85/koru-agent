"""
Test component configuration isolation after fixing architectural error.
"""
import asyncio
import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath('.'))

async def test_component_isolation():
    """Test component configuration isolation."""
    print("=== TEST COMPONENT CONFIGURATION ISOLATION ===")
    
    try:
        from core.config.app_config import AppConfig
        from core.components.base_component import BaseComponent
        from core.application.context.application_context import ApplicationContext
        from core.config.component_config import ComponentConfig
        
        print("[OK] Imports completed successfully")
        
        # Load configuration from registry
        app_config = AppConfig.from_registry(profile="prod")
        print("[OK] AppConfig successfully loaded from registry")
        
        # 1. Check that tool does NOT have skill prompts
        print("\n--- CHECKING TOOL ---")
        sql_tool_config = app_config.tool_configs["sql_tool"]
        print(f"SQL Tool config: {sql_tool_config}")
        
        assert sql_tool_config.prompt_versions == {}, \
            f"Expected empty dict, got: {sql_tool_config.prompt_versions}"
        print("[OK] Tool sql_tool has no prompts (correct)")
        
        # 2. Check that skill HAS only its own prompts
        print("\n--- CHECKING PLANNING SKILL ---")
        planning_config = app_config.skill_configs["planning"]
        print(f"Planning config: {planning_config}")
        
        assert "planning.create_plan" in planning_config.prompt_versions, \
            "Planning skill should have its own prompts"
        print("[OK] Planning skill has its own prompts")
        
        assert "book_library.search_books" not in planning_config.prompt_versions, \
            "Planning skill should not depend on library prompts!"
        print("[OK] Planning skill does not depend on other skills' prompts")
        
        # 3. Check that other skill also has only its own prompts
        print("\n--- CHECKING BOOK_LIBRARY SKILL ---")
        book_library_config = app_config.skill_configs["book_library"]
        print(f"Book Library config: {book_library_config}")
        
        assert "book_library.search_books" in book_library_config.prompt_versions, \
            "Library skill should have its own prompts"
        print("[OK] Book Library skill has its own prompts")
        
        assert "planning.create_plan" not in book_library_config.prompt_versions, \
            "Library skill should not depend on planning prompts!"
        print("[OK] Book Library skill does not depend on other skills' prompts")
        
        # 4. Create fake Application Context for initialization testing
        print("\n--- TESTING COMPONENT INITIALIZATION ---")
        
        class MockResource:
            def __init__(self):
                self.resources = {}
            
            def get_resource(self, name):
                if name not in self.resources:
                    # Create mock services
                    if name == "prompt_service":
                        class MockPromptService:
                            async def preload_prompts(self, config):
                                pass
                            
                            def get_prompt_from_cache(self, cap_name):
                                return f"Mock prompt for {cap_name}"
                        
                        self.resources[name] = MockPromptService()
                    elif name == "contract_service":
                        class MockContractService:
                            async def preload_contracts(self, config):
                                pass
                            
                            def get_contract_schema_from_cache(self, cap_name, direction="input"):
                                return {"mock": f"schema for {cap_name} {direction}"}
                        
                        self.resources[name] = MockContractService()
                    else:
                        self.resources[name] = None
                
                return self.resources[name]
        
        app_context = MockResource()
        
        # 5. Check successful initialization of tool without prompts
        print("Testing initialization of tool without prompts...")
        class MockTool(BaseComponent):
            async def execute(self, capability, parameters, context):
                pass
        
        tool = MockTool(name="sql_tool", application_context=app_context, component_config=sql_tool_config)
        init_result = await tool.initialize()
        
        assert init_result == True, "Tool should initialize without prompts"
        assert tool._initialized == True, "Tool initialization flag should be True"
        assert tool._cached_prompts == {}, "Tool prompts cache should be empty"
        print("[OK] Tool without prompts initialized successfully")
        
        # 6. Check skill initialization with prompts
        print("Testing initialization of skill with prompts...")
        skill = MockTool(name="planning", application_context=app_context, component_config=planning_config)
        init_result = await skill.initialize()
        
        assert init_result == True, "Skill should initialize with prompts"
        assert skill._initialized == True, "Skill initialization flag should be True"
        assert len(skill._cached_prompts) > 0, "Skill prompts cache should contain elements"
        assert "planning.create_plan" in skill._cached_prompts, "Skill should have its own prompts in cache"
        print("[OK] Skill with prompts initialized successfully")
        
        print("\n[SUCCESS] ALL TESTS PASSED! Component isolation works correctly!")
        print("\n=== TEST RESULTS ===")
        print("- Tools do not inherit skill prompts: OK")
        print("- Skills have only their own prompts: OK")
        print("- Components without prompts initialize successfully: OK")
        print("- Components with prompts initialize successfully: OK")
        print("- Caches are isolated: OK")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_component_isolation())
    if success:
        print("\n[SUCCESS] Testing completed successfully!")
    else:
        print("\n[ERROR] Testing completed with errors!")
        sys.exit(1)