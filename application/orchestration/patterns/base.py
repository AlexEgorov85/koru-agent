"""
Базовый класс для компонуемых паттернов.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.models.agent.agent_state import AgentState
from domain.models.provider_type import LLMResponse


class ComposablePattern(ABC):
    """Абстрактный базовый класс для компонуемых паттернов мышления."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Название паттерна."""
        pass

    @abstractmethod
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str],
        llm_response: Optional[LLMResponse] = None
    ):
        """Выполнить паттерн."""
        pass

    @abstractmethod
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче."""
        pass