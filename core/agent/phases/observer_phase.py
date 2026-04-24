"""
Observer Step: Observer.analyze() with LLM skip logic (Фаза 1).

Responsibility:
- Determine if LLM call is needed based on trigger_mode and result status
- Call observer.analyze() with force_llm flag
- Record metrics for LLM usage
- Update agent metrics based on observation
- Publish observation events

This step implements the cost optimization from Фаза 1.
"""

import logging
from typing import Any, Dict, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionStatus


class ObserverPhase:
    """Orchestrates the observation stage of the agent loop."""
    
    def __init__(
        self,
        observer: Any,
        metrics: Any,
        policy: Any,
        log: logging.Logger,
        event_bus: Any,
    ):
        self.observer = observer
        self.metrics = metrics
        self.policy = policy
        self.log = log
        self.event_bus = event_bus
    
    async def analyze(
        self,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        result_data: Any,
        error_msg: Optional[str],
        session_id: str,
        agent_id: str,
        step_number: int,
    ) -> Dict[str, Any]:
        """
        Analyze execution result through Observer.
        
        Args:
            decision_action: Action name from decision
            decision_parameters: Action parameters
            result_data: Result data from execution
            error_msg: Error message if failed
            session_id: Current session ID
            agent_id: Current agent ID
            step_number: Step number
            
        Returns:
            Observation dict from observer
        """
        self.log.info(
            f"👁️ Observer.analyze({decision_action})...",
            extra={"event_type": EventType.INFO},
        )
        
        # Determine result status
        result_status = None
        if hasattr(result_data, 'status'):
            result_status = result_data.status
        
        # Check if LLM call is needed (Фаза 1 optimization)
        should_call_llm = (
            self.observer.trigger_mode == "always" or
            result_status in (ExecutionStatus.FAILED, ExecutionStatus.EMPTY) or
            self.metrics.repeated_actions_count >= self.policy.max_repeated_actions
        )
        
        # Call observer
        observation = await self.observer.analyze(
            action_name=decision_action,
            parameters=decision_parameters or {},
            result=result_data,
            error=error_msg,
            session_id=session_id,
            agent_id=agent_id,
            step_number=step_number,
            force_llm=should_call_llm,
        )
        
        # Record metrics (Фаза 1)
        used_llm = not observation.get("_rule_based", False)
        self.metrics.record_observer_call(used_llm=used_llm)
        
        # Publish observation event with skip metric
        await self.event_bus.publish(
            EventType.DEBUG,
            {
                "event": "OBSERVATION",
                "status": observation.get("status"),
                "quality": observation.get("data_quality"),
                "rule_based": not used_llm,
                "observer_skip_rate": self.metrics.observer_skip_rate,
            },
            session_id=session_id,
            agent_id=agent_id,
        )
        
        # Update metrics based on observation
        status = observation.get("status", "unknown")
        self.metrics.add_step(
            action_name=decision_action,
            status=status,
            error=observation.get("errors", [None])[0] if observation.get("errors") else None,
        )
        self.metrics.update_observation(observation)
        
        # Log observation result
        self.log.info(
            f"📊 Observation: status={status}, quality={observation.get('data_quality', {})}",
            extra={"event_type": EventType.INFO},
        )
        
        # Check recommendations for next step
        if observation.get("requires_additional_action") and status in ["empty", "error"]:
            self.log.warning(
                f"⚠️ Observer рекомендует сменить стратегию: {observation.get('next_step_suggestion', '')}",
                extra={"event_type": EventType.INFO},
            )
        
        return observation
