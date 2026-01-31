from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from .base import AgentThinkingPatternInterface


class FallbackThinkingPattern(AgentThinkingPatternInterface):
    """
    Паттерн мышления безопасного завершения.
    Используется при критических ошибках.
    """

    name = "fallback"

    async def next_step(self, runtime):
        return StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason="fallback_triggered"
        )
