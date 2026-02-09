from abc import ABC, abstractmethod
from core.agent_runtime.interfaces import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision


class AgentStrategyInterface(ABC):
    """
    Базовый интерфейс стратегии.

    Стратегия:
    - анализирует состояние
    - принимает решение
    - НЕ исполняет действия
    """

    name: str

    @abstractmethod
    async def next_step(
        self,
        runtime: AgentRuntimeInterface
    ) -> StrategyDecision:
        """
        Вернуть решение на текущем шаге.
        """
        pass
