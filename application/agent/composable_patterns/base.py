"""
Базовый класс для компонуемых паттернов.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState


class ComposablePattern(IThinkingPattern):
    """
    Абстрактный базовый класс для компонуемых паттернов
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Название паттерна
        """
        pass

    @abstractmethod
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ):
        """
        Выполнить компонуемый паттерн

        Args:
            state: Состояние агента
            context: Контекст выполнения паттерна
            available_capabilities: Доступные возможности

        Returns:
            Результат выполнения паттерна
        """
        pass

    @abstractmethod
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптировать паттерн к задаче

        Args:
            task_description: Описание задачи

        Returns:
            Словарь с информацией об адаптации
        """
        pass