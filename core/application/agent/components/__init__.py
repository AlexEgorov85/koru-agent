"""
Инициализация компонентов агента для новой архитектуры
"""
from .behavior_manager import BehaviorManager
from .action_executor import ActionExecutor, ExecutionContext
from .model import StrategyDecision, StrategyDecisionType
from .policy import AgentPolicy
from .progress import ProgressScorer
from .state import AgentState
from .error_classifier import ErrorClassifier
from .failure_memory import FailureMemory, FailureRecord
from .safe_executor import SafeExecutor


__all__ = [
    'BehaviorManager',
    'ActionExecutor',
    'ExecutionContext',
    'StrategyDecision',
    'StrategyDecisionType',
    'AgentPolicy',
    'ProgressScorer',
    'AgentState',
    'ErrorClassifier',
    'FailureMemory',
    'FailureRecord',
    'SafeExecutor'
]