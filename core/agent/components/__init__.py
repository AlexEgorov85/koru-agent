"""
Модуль компонентов агента.

КОМПОНЕНТЫ:
- action_executor: исполнитель действий
- observer: наблюдатель за результатами
- safe_executor: безопасный исполнитель с retry
- policy: политика агента
- agent_metrics: метрики агента

USAGE:
```python
from core.agent.components import ActionExecutor
```
"""
from .action_executor import ActionExecutor, ExecutionContext
from .observer import Observer
from .safe_executor import SafeExecutor
from .policy import AgentPolicy, RetryPolicy
from .agent_metrics import AgentMetrics
from .sql_recovery import SQLRecoveryAnalyzer
from .observation_signal import ObservationSignalService

__all__ = [
    'ActionExecutor',
    'ExecutionContext',
    'Observer',
    'SafeExecutor',
    'AgentPolicy',
    'RetryPolicy',
    'AgentMetrics',
    'SQLRecoveryAnalyzer',
    'ObservationSignalService',
]
