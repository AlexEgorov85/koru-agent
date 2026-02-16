import tempfile
from pathlib import Path
import json
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.data.prompt import Prompt, PromptStatus, ComponentType

# Test 8: Delete nonexistent prompt
with tempfile.TemporaryDirectory() as tmp_dir:
    base_dir = Path(tmp_dir)
    registry_config = RegistryConfig(
        profile='dev',
        capability_types={'test.skill': 'skill'}
    )
    
    ds = FileSystemDataSource(base_dir, registry_config)
    ds.initialize()
    
    # Try to delete nonexistent prompt
    try:
        ds.delete_prompt("non.existent:v1.0.0")
        print('Test 8 failed: delete_prompt() did not raise an exception for nonexistent prompt')
    except Exception as e:
        print(f'Test 8 passed: delete_prompt() raised {type(e).__name__}: {e}')