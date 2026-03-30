"""
Fallback Strategy Service - стратегии fallback для behavior паттернов.

Используется для обработки ошибок и переключения между паттернами.
"""
from typing import Dict, Any, List, Optional
from core.agent.behaviors.base import Decision, DecisionType
from core.models.data.capability import Capability


class FallbackStrategyService:
    """Стратегии fallback для behavior паттернов."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {
            "max_retries": 3,
            "default_pattern": "fallback.v1.0.0",
            "emergency_stop": True
        }

    def create_retry(self, reason: str, max_retries: Optional[int] = None) -> Decision:
        """Создаёт решение для повторной попытки (теперь это ACT)."""
        return Decision(
            type=DecisionType.ACT,
            action="retry",
            reasoning=reason,
            confidence=0.5
        )

    def create_switch(self, next_pattern: str, reason: str) -> Decision:
        """Создаёт решение для переключения паттерна."""
        return Decision(
            type=DecisionType.SWITCH_STRATEGY,
            next_pattern=next_pattern,
            error=reason,
            confidence=0.7
        )

    def create_stop(self, reason: str, final_answer: Optional[str] = None) -> Decision:
        """Создаёт решение для остановки."""
        return Decision(
            type=DecisionType.FAIL,
            error=reason,
            confidence=0.9
        )

    def create_error(
        self,
        reason: str,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Создаёт решение при ошибке."""
        if available_capabilities:
            cap = available_capabilities[0]
            return Decision(
                type=DecisionType.ACT,
                action=cap.name,
                parameters={},
                reasoning=f"fallback_{reason}",
                confidence=0.3
            )
        return Decision(
            type=DecisionType.FAIL,
            error=f"emergency_stop_no_capabilities_{reason}",
            confidence=0.1
        )

    def create_reasoning_fallback(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        reason: str
    ) -> Dict[str, Any]:
        """Создаёт fallback-результат рассуждения."""
        fallback_capability = (
            available_capabilities[0].name
            if available_capabilities
            else "final_answer.generate"
        )
        return {
            "thought": f"Fallback из-за: {reason}",
            "analysis": {
                "progress": "Неизвестно",
                "current_state": f"Fallback: {reason}",
                "issues": []
            },
            "decision": {
                "next_action": fallback_capability,
                "reasoning": f"fallback после ошибки: {reason}",
                "parameters": {},
                "expected_outcome": "Неизвестно"
            },
            "confidence": 0.3,
            "stop_condition": False,
            "stop_reason": "fallback",
            "alternative_actions": []
        }
