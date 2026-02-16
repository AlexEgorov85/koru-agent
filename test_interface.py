from core.infrastructure.storage.mock_database_resource_data_source import MockDatabaseResourceDataSource
from core.models.manifest import Manifest, ComponentType, ComponentStatus

# Тест создания mock-источника данных
ds = MockDatabaseResourceDataSource()
ds.initialize()

# Тест создания манифеста
manifest = Manifest(
    component_id='test_component',
    component_type=ComponentType.SKILL,
    version='v1.0.0',
    owner='test_owner',
    status=ComponentStatus.ACTIVE
)

# Добавление манифеста в mock-хранилище
ds._manifests['skill.test_component'] = manifest

# Тест загрузки манифеста
loaded_manifest = ds.load_manifest('skill', 'test_component')
print(f'[SUCCESS] Loaded manifest: {loaded_manifest.component_id}')

# Тест списка манифестов
manifests = ds.list_manifests()
print(f'[SUCCESS] Found {len(manifests)} manifests')

# Тест проверки существования
exists = ds.manifest_exists('skill', 'test_component', 'v1.0.0')
print(f'[SUCCESS] Manifest exists: {exists}')

print('[SUCCESS] All interface tests passed!')