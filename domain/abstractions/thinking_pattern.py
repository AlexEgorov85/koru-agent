"""
Интерфейс для компонуемых паттернов мышления.
"""
from abc import ABC, abstractmethod
from typing import Any, List, Dict
from domain.models.agent.agent_state import AgentState


class IThinkingPattern(ABC):
    """Интерфейс для компонуемых паттернов мышления.
    
    ПАТЕРН МЫШЛЕНИЯ = что делать (планирование, выбор действия, анализ)
    РАНТАЙМ = как выполнять (оркестрация, управление состоянием)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя паттерна мышления."""
        pass
    
    @abstractmethod
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления.
        
        ВОЗВРАЩАЕТ:
            Dict с результатом выполнения паттерна
        """
        pass
    
    @abstractmethod
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче (выбор домена, настройка параметров)."""
        pass
