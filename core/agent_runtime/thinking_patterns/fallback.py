from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from .base import AgentThinkingPatternInterface


class FallbackThinkingPattern(AgentThinkingPatternInterface):
    """
    Паттерн мышления безопасного завершения.
    Используется при критических ошибках.
    """

    name = "fallback"

    async def next_step(self, runtime: AgentRuntimeInterface) -> StrategyDecision:
        return StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason="fallback_triggered"
        )
