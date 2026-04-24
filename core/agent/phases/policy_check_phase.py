"""
Policy Check Step: Policy.evaluate() with Fail-Fast.

Responsibility:
- Check loop conditions (repeated actions, empty results)
- Validate action against policy rules
- Raise PolicyViolationError on violations
- Return True if action is allowed

This step implements SRP: only policy validation, no side effects.
"""

import logging
from typing import Any, Dict, Optional

from core.agent.components.policy import AgentPolicy, PolicyViolationError
from core.session_context.session_context import SessionContext
from core.infrastructure.event_bus.unified_event_bus import EventType


class PolicyCheckPhase:
    """Orchestrates policy validation stage of the agent loop."""
    
    def __init__(self, policy: AgentPolicy, log: logging.Logger, event_bus: Any):
        self.policy = policy
        self.log = log
        self.event_bus = event_bus
    
    def check_loop_conditions(
        self,
        session_context: SessionContext,
        metrics: Any,
        step_number: int,
        agent_config: Optional[Any] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if agent should stop based on metrics and config.
        
        Args:
            session_context: Current session context
            metrics: AgentMetrics instance
            step_number: Current step number
            agent_config: Optional agent config for token budget
            
        Returns:
            Tuple of (should_stop: bool, reason: Optional[str])
        """
        # Check metrics-based conditions
        should_stop, stop_reason = metrics.should_stop()
        
        if should_stop:
            return True, stop_reason
        
        # Check token budget (Фаза 3)
        if agent_config and hasattr(agent_config, 'max_total_tokens'):
            if metrics.total_tokens_used >= agent_config.max_total_tokens:
                return True, f"Token budget exhausted: {metrics.total_tokens_used}/{agent_config.max_total_tokens}"
        
        # Check context size and compress if needed (Фаза 3)
        if agent_config and hasattr(agent_config, 'context_token_threshold'):
            context_tokens = session_context.get_context_token_estimate()
            if context_tokens > agent_config.context_token_threshold:
                # Compress context
                tokens_before, tokens_after = session_context.compress_history(
                    max_tokens=agent_config.context_token_threshold,
                    preserve_last_n=5
                )
                # Log compression event (caller will publish to event bus)
        
        return False, None
    
    def validate_action(
        self,
        action_name: str,
        metrics: Any,
        session_context: SessionContext,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Validate action through policy.evaluate().
        
        Args:
            action_name: Name of the action to validate
            metrics: AgentMetrics instance
            session_context: Current session context
            parameters: Optional action parameters
            
        Returns:
            True if action is allowed
            
        Raises:
            PolicyViolationError: If action violates policy rules
        """
        agent_state = session_context.agent_state
        
        self.policy.evaluate(
            action_name=action_name,
            metrics=metrics,
            state_data={
                "consecutive_repeated_actions": agent_state.consecutive_repeated_actions,
                "consecutive_empty_results": agent_state.consecutive_empty_results,
            },
            parameters=parameters or {},
        )
        
        return True
    
    def handle_violation(
        self,
        error: PolicyViolationError,
        decision_action: Optional[str],
        step_number: int,
        session_context: SessionContext,
        event_bus: Any = None,
    ) -> str:
        """
        Handle policy violation by logging and registering blocked action.
        
        Args:
            error: PolicyViolationError instance
            decision_action: Action that was blocked
            step_number: Current step number
            session_context: Session context for registration
            event_bus: Optional event bus for publishing
            
        Returns:
            Policy message string
        """
        policy_msg = f"POLICY_BLOCKED: {', '.join(error.verdict.violations)}. Действие отклонено. Смени инструмент или параметры."
        
        self.log.warning(
            f"⛔ Policy заблокировал действие {decision_action}: {policy_msg}",
            extra={"event_type": EventType.WARNING},
        )
        
        # Register blocked action in agent state
        session_context.agent_state.register_step_outcome(
            action_name=decision_action or "unknown",
            status="blocked",
            parameters={},
            observation={"status": "blocked", "reason": policy_msg},
            error_message=policy_msg,
        )
        
        # Add to step context for history
        from core.models.data.execution import ExecutionStatus
        
        session_context.register_step(
            step_number=step_number,
            capability_name=decision_action or "unknown",
            skill_name="",
            action_item_id=None,
            observation_item_ids=[],
            summary=f"Action blocked by policy: {policy_msg}",
            status=ExecutionStatus.FAILED,
            parameters={},
        )
        
        session_context.record_action(
            action_data={
                "action": decision_action,
                "parameters": {},
                "status": "blocked",
                "reason": policy_msg,
            },
            step_number=step_number,
        )
        
        return policy_msg
