import yaml
from pathlib import Path
from core.models.data.manifest import Manifest

manifests_dir = Path('data/manifests')
errors = []

for manifest_file in manifests_dir.rglob('manifest.yaml'):
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)
        manifest = Manifest(**raw)
        print(f'[SUCCESS] {manifest_file.relative_to(manifests_dir)} - {manifest.component_id} ({manifest.version})')
    except Exception as e:
        errors.append(f'{manifest_file}: {e}')
        print(f'[ERROR] {manifest_file}: {e}')

if errors:
    print(f'\n{len(errors)} errors found')
    exit(1)
else:
    print(f'\nAll manifests are valid!')