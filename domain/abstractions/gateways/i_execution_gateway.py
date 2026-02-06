"""
Интерфейс шлюза выполнения для инверсии зависимостей.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from domain.models.capability import Capability
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.models.execution.execution_result import ExecutionResult


class IExecutionGateway(ABC):
    """Интерфейс шлюза выполнения для инверсии зависимостей."""

    @abstractmethod
    async def execute_capability(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int = 0
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        
        Args:
            capability: Объект capability для выполнения
            parameters: Параметры для выполнения
            session: Контекст сессии
            step_number: Номер шага (для отслеживания)
            
        Returns:
            ExecutionResult с результатом выполнения
        """
        pass