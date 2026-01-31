from abc import ABC, abstractmethod
from typing import Union
from core.agent_runtime.interfaces import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision
from core.agent_runtime.execution_context import ExecutionContext


class AgentThinkingPatternInterface(ABC):
    """
    Базовый интерфейс паттерна мышления.

    Паттерн мышления:
    - анализирует состояние
    - принимает решение
    - НЕ исполняет действия
    """

    name: str

    @abstractmethod
    async def next_step(
        self,
        runtime: Union[AgentRuntimeInterface, ExecutionContext]
    ) -> StrategyDecision:
        """
        Вернуть решение на текущем шаге.
        """
        pass
