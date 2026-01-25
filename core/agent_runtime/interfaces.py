from abc import ABC, abstractmethod
from typing import Optional, Any
from .model import StrategyDecision


class AgentRuntimeInterface(ABC):
    """
    ЧИСТЫЙ контракт runtime, доступный стратегиям.
    """

    @abstractmethod
    async def call_llm(self, prompt: str) -> str:
        pass

    @abstractmethod
    def get_capability(self, name: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def execute_capability(self, cap: Any, parameters: dict) -> Any:
        pass

    @abstractmethod
    def session(self) -> Any:
        pass

    @abstractmethod
    def state(self) -> Any:
        pass


class AgentStrategyInterface(ABC):
    """
    Интерфейс стратегий.
    """

    name: str

    @abstractmethod
    async def next_step(
        self,
        runtime: AgentRuntimeInterface
    ) -> StrategyDecision:
        pass
