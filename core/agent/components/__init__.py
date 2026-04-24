"""
Модуль компонентов агента.

КОМПОНЕНТЫ:
- observer: наблюдатель за результатами
- safe_executor: безопасный исполнитель с retry
- policy: политика агента
- agent_metrics: метрики агента

NOTE: ActionExecutor и ExecutionContext перенесены в core.components.action_executor
"""

from core.components.action_executor import ActionExecutor, ExecutionContext

from .observer import Observer
from .safe_executor import SafeExecutor
from .policy import AgentPolicy, RetryPolicy
from .agent_metrics import AgentMetrics
from .sql_recovery import SQLRecoveryAnalyzer

__all__ = [
    'ActionExecutor',
    'ExecutionContext',
    'Observer',
    'SafeExecutor',
    'AgentPolicy',
    'RetryPolicy',
    'AgentMetrics',
    'SQLRecoveryAnalyzer',
]
