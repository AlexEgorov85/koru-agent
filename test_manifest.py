from core.models.manifest import Manifest, ComponentType, ComponentStatus

# Тест валидного манифеста
m = Manifest(
    component_id='test',
    component_type=ComponentType.SKILL,
    version='v1.0.0',
    owner='test_owner',
    status=ComponentStatus.ACTIVE
)
print(f'[SUCCESS] Manifest created: {m.component_id}@{m.version}')

# Тест невалидной версии
try:
    Manifest(
        component_id='test',
        component_type=ComponentType.SKILL,
        version='1.0.0',  # Без 'v'
        owner='owner',
        status=ComponentStatus.ACTIVE
    )
    print('[ERROR] Should have failed validation for version')
except Exception as e:
    print(f'[SUCCESS] Version without v rejected: {e}')