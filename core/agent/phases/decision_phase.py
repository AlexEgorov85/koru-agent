"""
Decision Step: Pattern.decide() orchestration.

Responsibility:
- Get current agent state
- Call pattern.decide() with session context and capabilities
- Log decision details
- Return Decision object

This is a READONLY operation - Pattern contains only prompts and contracts.
"""

import logging
from typing import Any, Dict, List, Optional

from core.agent.behaviors.base import Decision
from core.session_context.session_context import SessionContext
from core.infrastructure.event_bus.unified_event_bus import EventType


class DecisionPhase:
    """Orchestrates the decision-making stage of the agent loop."""
    
    def __init__(self, log: logging.Logger, event_bus: Any):
        self.log = log
        self.event_bus = event_bus
    
    async def execute(
        self,
        pattern: Any,
        session_context: SessionContext,
        available_capabilities: List[str],
        step_number: int,
    ) -> Decision:
        """
        Execute decision step.
        
        Args:
            pattern: Pattern instance (ReActPattern or other)
            session_context: Current session context with history
            available_capabilities: List of available capability names
            step_number: Current step number for logging
            
        Returns:
            Decision object from pattern.decide()
        """
        self.log.info(
            "🤔 Анализирую запрос и выбираю следующее действие...",
            extra={"event_type": EventType.AGENT_THINKING},
        )
        
        self.log.info(
            "🧠 Pattern.decide()...",
            extra={"event_type": EventType.AGENT_DECISION},
        )
        
        decision = await pattern.decide(
            session_context=session_context,
            available_capabilities=available_capabilities,
        )
        
        # Format decision message
        decision_msg = (
            f"✅ Pattern вернул: type={decision.type.value}"
            + (f", action={decision.action}" if decision.action else "")
            + (f", reasoning: {decision.reasoning}" if decision.reasoning else "")
        )
        
        self.log.info(
            decision_msg,
            extra={"event_type": EventType.AGENT_DECISION},
        )
        
        # Publish decision event
        await self.event_bus.publish(
            EventType.CAPABILITY_SELECTED,
            {
                "capability": decision.action,
                "pattern": decision.type.value,
                "reasoning": decision.reasoning or "",
                "step": step_number,
            },
            session_id=session_context.session_id,
            agent_id=session_context.agent_id,
        )
        
        # Log for UI
        self.log.info(
            f"🎯 Capability: {decision.action} | {decision.reasoning or ''}",
            extra={"event_type": EventType.AGENT_DECISION},
        )
        
        return decision
