import tempfile
from pathlib import Path
import json
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig

# Test 3: Corrupted JSON
with tempfile.TemporaryDirectory() as tmp_dir:
    base_dir = Path(tmp_dir)
    registry_config = RegistryConfig(
        profile='dev',
        capability_types={'test.skill': 'skill'}
    )
    
    # Create prompts directory
    prompts_dir = base_dir / 'prompts' / 'skill' / 'test'
    prompts_dir.mkdir(parents=True)
    
    # Create corrupted JSON file
    prompt_file = prompts_dir / 'test.skill_v1.0.0.json'
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write('{ invalid json ')  # intentionally broken JSON
    
    ds = FileSystemDataSource(base_dir, registry_config)
    
    try:
        ds.initialize()
        print('Test 3 failed: initialize() did not raise an exception')
    except Exception as e:
        print(f'Test 3 passed: initialize() raised {type(e).__name__}: {e}')