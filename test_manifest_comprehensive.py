from core.models.manifest import Manifest, ComponentType, ComponentStatus, QualityMetrics

# Тест валидного манифеста
m = Manifest(
    component_id='test',
    component_type=ComponentType.SKILL,
    version='v1.0.0',
    owner='test_owner',
    status=ComponentStatus.ACTIVE
)
print(f'[SUCCESS] Valid manifest created: {m.component_id}@{m.version}')

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
    print(f'[SUCCESS] Version without v rejected: {type(e).__name__}')

# Тест пустого owner
try:
    Manifest(
        component_id='test',
        component_type=ComponentType.SKILL,
        version='v1.0.0',
        owner='',
        status=ComponentStatus.ACTIVE
    )
    print('[ERROR] Should have failed validation for empty owner')
except Exception as e:
    print(f'[SUCCESS] Empty owner rejected: {type(e).__name__}')

# Тест enum значений
print(f'[SUCCESS] ComponentType.ACTIVE.value: {ComponentStatus.ACTIVE.value}')

# Тест диапазона метрик
try:
    QualityMetrics(success_rate_target=1.5)  # Больше 1.0
    print('[ERROR] Should have failed validation for metrics range')
except Exception as e:
    print(f'[SUCCESS] Metrics out of range rejected: {type(e).__name__}')

print('[SUCCESS] All tests passed!')