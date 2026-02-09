from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from .base import AgentStrategyInterface


class EvaluationStrategy(AgentStrategyInterface):
    """
    Оценка достижения цели.
    """

    name = "evaluation"

    async def next_step(self, runtime):
        session = runtime.session()

        prompt = f"""
Цель:
{session.goal}

Результаты:
{session.get_summary()}

Ответь строго:
- "ДА" если цель достигнута
- "НЕТ" если нет
"""

        answer = await runtime.call_llm(prompt)

        if "да" in answer.lower():
            return StrategyDecision(
                action=StrategyDecisionType.STOP,
                reason="goal_achieved"
            )

        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="react",
            reason="goal_not_achieved"
        )
