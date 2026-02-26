"""
Модуль наблюдаемости (Observability).

КОМПОНЕНТЫ:
- observability_manager: единая точка для метрик, логов и health check

USAGE:
```python
from core.observability import (
    ObservabilityManager,
    HealthStatus,
    get_observability_manager,
    create_observability_manager,
)

# Использование
obs_manager = get_observability_manager()
await obs_manager.initialize()

# Запись операции
await obs_manager.record_operation(
    operation="execute",
    component="skill",
    duration_ms=100,
    success=True,
)

# Health check
health = await obs_manager.get_health_status()

# Статистика
stats = obs_manager.get_stats()
```
"""
from .observability_manager import (
    ObservabilityManager,
    HealthChecker,
    HealthStatus,
    ComponentType,
    HealthCheckResult,
    OperationMetrics,
    get_observability_manager,
    create_observability_manager,
    reset_observability_manager,
)

__all__ = [
    'ObservabilityManager',
    'HealthChecker',
    'HealthStatus',
    'ComponentType',
    'HealthCheckResult',
    'OperationMetrics',
    'get_observability_manager',
    'create_observability_manager',
    'reset_observability_manager',
]
