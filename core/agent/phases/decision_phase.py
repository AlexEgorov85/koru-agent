"""
Фаза принятия решений: оркестрация Pattern.decide().

Ответственность:
- Получить текущее состояние агента
- Вызвать pattern.decide() с контекстом сессии и возможностями
- Логировать детали решения
- Возвращать объект Decision

Это операция ТОЛЬКО ДЛЯ ЧТЕНИЯ - Pattern содержит только промпты и контракты.
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
        reasoning_short = ""
        if decision.reasoning_detail:
            reasoning_short = (
                decision.reasoning_detail.get("analysis_final")
                or decision.reasoning_detail.get("analysis_progress")
                or ""
            )
        
        decision_msg = (
            f"✅ Pattern вернул: type={decision.type.value}"
            + (f", action={decision.action}" if decision.action else "")
            + (f", reasoning: {reasoning_short}" if reasoning_short else "")
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
                "reasoning_detail": decision.reasoning_detail or {},
                "step": step_number,
            },
            session_id=session_context.session_id,
            agent_id=session_context.agent_id,
        )
        
        # Log for UI
        reasoning_short = ""
        if decision.reasoning_detail:
            reasoning_short = (
                decision.reasoning_detail.get("analysis_final")
                or decision.reasoning_detail.get("analysis_progress")
                or ""
            )
        
        self.log.info(
            f"🎯 Capability: {decision.action} | {reasoning_short or ''}",
            extra={"event_type": EventType.AGENT_DECISION},
        )
        
        return decision
