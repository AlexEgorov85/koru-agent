import tempfile
from pathlib import Path
import json
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.prompt import Prompt, PromptStatus, ComponentType

# Test 6: Duplicate prompt error
with tempfile.TemporaryDirectory() as tmp_dir:
    base_dir = Path(tmp_dir)
    registry_config = RegistryConfig(
        profile='dev',
        capability_types={'test.skill': 'skill'}
    )
    
    ds = FileSystemDataSource(base_dir, registry_config)
    ds.initialize()
    
    # Create and save first prompt
    prompt1 = Prompt(
        capability="test.skill",
        version="v1.0.0",
        status=PromptStatus.ACTIVE,
        component_type=ComponentType.SKILL,
        content="This is a test prompt with variable {var1}",
        variables=[
            {
                "name": "var1",
                "description": "Test variable",
                "required": True
            }
        ]
    )
    
    ds.save_prompt(prompt1)
    
    # Try to save second with same name
    prompt2 = Prompt(
        capability="test.skill",  # same capability
        version="v1.0.0",        # same version
        status=PromptStatus.DRAFT,
        component_type=ComponentType.SKILL,
        content="This is another test prompt",
        variables=[]
    )
    
    try:
        ds.save_prompt(prompt2)
        print('Test 6 failed: save_prompt() did not raise an exception for duplicate')
    except Exception as e:
        print(f'Test 6 passed: save_prompt() raised {type(e).__name__}: {e}')