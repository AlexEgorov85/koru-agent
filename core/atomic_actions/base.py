"""
Base classes for atomic actions in the agent architecture.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

# Используем TYPE_CHECKING для предотвращения циклических импортов
if TYPE_CHECKING:
    from core.agent_runtime.runtime_interface import AgentRuntimeInterface
    from core.agent_runtime.model import StrategyDecision

from core.agent_runtime.runtime_interface import AgentRuntimeInterface  # Импорт для выполнения, не для типизации
from core.agent_runtime.model import StrategyDecision  # Также импортируем для выполнения


class AtomicActionType(Enum):
    """Enumeration of atomic action types."""
    THINK = "think"       # размышление
    ACT = "act"           # действие
    OBSERVE = "observe"   # наблюдение
    PLAN = "plan"         # планирование
    REFLECT = "reflect"   # рефлексия
    EVALUATE = "evaluate" # оценка
    VERIFY = "verify"     # проверка
    ADAPT = "adapt"       # адаптация


class AtomicAction(ABC):
    """
    Abstract base class for atomic actions.
    
    Atomic actions are the fundamental building blocks that can be composed
    to create complex thinking patterns.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the atomic action.
        
        Args:
            runtime: The agent runtime interface
            context: The execution context
            parameters: Optional parameters for the action
            
        Returns:
            StrategyDecision representing the outcome
        """
        pass
