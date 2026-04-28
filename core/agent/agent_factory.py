"""
AgentFactory — фабрика для создания всех компонентов и фаз AgentRuntime.

АРХИТЕКТУРА:
- Инкапсулирует логику инициализации executor, policies, metrics, observer, всех фаз
- Runtime получает готовые компоненты через ссылки
- Упрощает тестирование (можно подменять фабрику или мокать компоненты)
"""

from typing import Any, Dict, Optional

from core.agent.components.sql_recovery import SQLRecoveryAnalyzer
from core.components.action_executor import ActionExecutor
from core.agent.components.safe_executor import SafeExecutor
from core.errors.failure_memory import FailureMemory
from core.agent.components.policy import AgentPolicy
from core.agent.components.agent_metrics import AgentMetrics
from core.agent.components.observer import Observer
from core.agent.components.sql_diagnostic import SQLDiagnosticService

from core.agent.phases.decision_phase import DecisionPhase
from core.agent.phases.policy_check_phase import PolicyCheckPhase
from core.agent.phases.execution_phase import ExecutionPhase
from core.agent.phases.observation_phase import ObservationPhase
from core.agent.phases.context_update_phase import ContextUpdatePhase
from core.agent.phases.final_answer_phase import FinalAnswerPhase
from core.agent.phases.error_recovery_phase import ErrorRecoveryPhase
from core.agent.phases.validation_phase import ValidationPhase

from core.agent.behaviors.services import FallbackStrategyService

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.config.agent_config import AgentConfig


class AgentComponents:
    """Контейнер для всех созданных компонентов агента."""
    
    def __init__(
        self,
        executor: ActionExecutor,
        failure_memory: FailureMemory,
        policy: AgentPolicy,
        metrics: AgentMetrics,
        observer: Observer,
        fallback_strategy: FallbackStrategyService,
        safe_executor: SafeExecutor,
        decision_phase: DecisionPhase,
        policy_check_phase: PolicyCheckPhase,
        execution_phase: ExecutionPhase,
        observation_phase: ObservationPhase,
        context_update_phase: ContextUpdatePhase,
        final_answer_phase: FinalAnswerPhase,
        error_recovery_phase: ErrorRecoveryPhase,
        validation_phase: ValidationPhase,
        sql_diagnostic: Optional[SQLDiagnosticService] = None,
    ):
        self.executor = executor
        self.failure_memory = failure_memory
        self.policy = policy
        self.metrics = metrics
        self.observer = observer
        self.fallback_strategy = fallback_strategy
        self.safe_executor = safe_executor
        self.decision_phase = decision_phase
        self.policy_check_phase = policy_check_phase
        self.execution_phase = execution_phase
        self.observation_phase = observation_phase
        self.context_update_phase = context_update_phase
        self.final_answer_phase = final_answer_phase
        self.error_recovery_phase = error_recovery_phase
        self.validation_phase = validation_phase
        self.sql_diagnostic = sql_diagnostic


class AgentFactory:
    """Фабрика для создания всех компонентов AgentRuntime."""

    @staticmethod
    def create_components(
        application_context: Any,
        agent_config: Optional[AgentConfig],
        log: Any,
        event_bus: Any,
    ) -> AgentComponents:
        """
        Создает все компоненты и фазы для AgentRuntime.

        ARGS:
            application_context: контекст приложения
            agent_config: конфигурация агента
            log: логгер агента
            event_bus: шина событий

        RETURNS:
            AgentComponents: контейнер со всеми созданными компонентами
        """
        # Базовые компоненты
        executor = ActionExecutor(application_context)
        failure_memory = FailureMemory()
        policy = AgentPolicy()
        metrics = AgentMetrics()

        # Observer с настройкой trigger_mode
        observer_trigger_mode = "always"
        if application_context and hasattr(application_context, 'config'):
            app_cfg = application_context.config
            if hasattr(app_cfg, 'agent_defaults') and hasattr(app_cfg.agent_defaults, 'observer_trigger_mode'):
                observer_trigger_mode = app_cfg.agent_defaults.observer_trigger_mode
        observer = Observer(application_context, trigger_mode=observer_trigger_mode)

        # Fallback strategy
        from core.agent.behaviors.services import FallbackStrategyService
        fallback_strategy = FallbackStrategyService()

        # Safe executor
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=policy.max_retries,
            base_delay=policy.retry_base_delay,
            max_delay=policy.retry_max_delay,
        )

        # Фазы
        decision_phase = DecisionPhase(
            log=log,
            event_bus=event_bus,
        )

        policy_check_phase = PolicyCheckPhase(
            policy=policy,
            log=log,
            event_bus=event_bus,
        )

        execution_phase = ExecutionPhase(
            safe_executor=safe_executor,
            log=log,
            event_bus=event_bus,
            agent_config=agent_config,
        )

        observation_phase = ObservationPhase(
            observer=observer,
            metrics=metrics,
            policy=policy,
            log=log,
            event_bus=event_bus,
        )

        # SQL diagnostic для error recovery
        sql_diagnostic = None
        try:
            sql_diagnostic = SQLDiagnosticService(application_context)
        except Exception:
            pass

        error_recovery_phase = ErrorRecoveryPhase(
            sql_diagnostic_service=sql_diagnostic,
            log=log,
        )

        context_update_phase = ContextUpdatePhase(
            log=log,
            event_bus=event_bus,
            error_recovery_handler=error_recovery_phase,
        )
        
        validation_phase = ValidationPhase(
            log=log,
            event_bus=event_bus,
        )
        
        final_answer_phase = FinalAnswerPhase(
            application_context=application_context,
            executor=executor,
            agent_config=agent_config,
            log=log,
            event_bus=event_bus,
        )

        return AgentComponents(
            executor=executor,
            failure_memory=failure_memory,
            policy=policy,
            metrics=metrics,
            observer=observer,
            fallback_strategy=fallback_strategy,
            safe_executor=safe_executor,
            decision_phase=decision_phase,
            policy_check_phase=policy_check_phase,
            execution_phase=execution_phase,
            observation_phase=observation_phase,
            context_update_phase=context_update_phase,
            final_answer_phase=final_answer_phase,
            error_recovery_phase=error_recovery_phase,
            validation_phase=validation_phase,
            sql_diagnostic=sql_diagnostic,
        )
