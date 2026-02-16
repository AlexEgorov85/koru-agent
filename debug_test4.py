import tempfile
from pathlib import Path
import json
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.prompt import Prompt, PromptStatus, ComponentType

# Test 4: Invalid Prompt
with tempfile.TemporaryDirectory() as tmp_dir:
    base_dir = Path(tmp_dir)
    registry_config = RegistryConfig(
        profile='dev',
        capability_types={'test.skill': 'skill'}
    )
    
    # Create prompts directory
    prompts_dir = base_dir / 'prompts' / 'skill' / 'test'
    prompts_dir.mkdir(parents=True)
    
    # Create invalid prompt file (too short content)
    prompt_data = {
        "capability": "test.skill",
        "version": "v1.0.0",
        "status": "active",
        "component_type": "skill",
        "content": "Too short",  # too short content
        "variables": []
    }
    
    prompt_file = prompts_dir / 'test.skill_v1.0.0.json'
    with open(prompt_file, 'w', encoding='utf-8') as f:
        json.dump(prompt_data, f, ensure_ascii=False, indent=2)
    
    ds = FileSystemDataSource(base_dir, registry_config)
    
    try:
        ds.initialize()
        print('Test 4 failed: initialize() did not raise an exception')
    except Exception as e:
        print(f'Test 4 passed: initialize() raised {type(e).__name__}: {e}')