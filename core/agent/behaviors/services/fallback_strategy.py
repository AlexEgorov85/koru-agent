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

    def create_error(
        self,
        reason: str,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Создаёт решение при ошибке - всегда FAIL, не продолжаем как ни в чём не бывало."""
        return Decision(
            type=DecisionType.FAIL,
            error=f"llm_error: {reason}",
            reasoning=f"Ошибка при генерации решения: {reason}",
            confidence=0.0
        )

    def create_reasoning_fallback(
        self,
        context: Dict[str, Any],
        available_capabilities: List[Capability],
        reason: str
    ) -> Decision:
        """Fallback для генерации решения через LLM."""
        return Decision(
            type=DecisionType.FAIL,
            error=f"llm_reasoning_error: {reason}",
            reasoning=f"Не удалось сгенерировать решение: {reason}",
            confidence=0.0
        )
