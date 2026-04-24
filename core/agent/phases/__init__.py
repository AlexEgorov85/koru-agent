"""
Phase handlers for AgentRuntime cycle.

Каждый модуль фазы инкапсулирует отдельный этап в рамках одного шага агента:
- decision_phase: логика Pattern.decide()
- policy_check_phase: Policy.evaluate() с Fail-Fast проверками
- execution_phase: SafeExecutor.execute() с обработкой результатов
- observer_phase: Observer.analyze() с логикой пропуска LLM (Фаза 1)
- context_update_phase: регистрация в SessionContext и обновление состояния
- final_answer_phase: генерация финального ответа (FINISH или fallback)
- error_recovery_phase: SQL диагностика и обработка пустых результатов
"""

from core.agent.phases.decision_phase import DecisionPhase
from core.agent.phases.policy_check_phase import PolicyCheckPhase
from core.agent.phases.execution_phase import ExecutionPhase
from core.agent.phases.observer_phase import ObserverPhase
from core.agent.phases.context_update_phase import ContextUpdatePhase
from core.agent.phases.final_answer_phase import FinalAnswerPhase
from core.agent.phases.error_recovery_phase import ErrorRecoveryPhase

__all__ = [
    'DecisionPhase',
    'PolicyCheckPhase',
    'ExecutionPhase',
    'ObserverPhase',
    'ContextUpdatePhase',
    'FinalAnswerPhase',
    'ErrorRecoveryPhase',
]
