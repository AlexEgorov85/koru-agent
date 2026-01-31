"""
Interfaces for the agent runtime with support for new architecture.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, TYPE_CHECKING

# Используем TYPE_CHECKING для предотвращения циклических импортов
if TYPE_CHECKING:
    from core.atomic_actions.base import AtomicAction
    from core.composable_patterns.base import ComposablePattern

from core.atomic_actions.base import AtomicAction  # Импорт для выполнения, не для типизации
from core.composable_patterns.base import ComposablePattern  # Также импорт для выполнения


class ComposableAgentInterface(ABC):
    """
    Interface for agents that support composable patterns.
    """
    
    @abstractmethod
    async def execute_atomic_action(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Execute an atomic action.
        """
        ...
    
    @abstractmethod
    async def execute_composable_pattern(
        self,
        pattern: ComposablePattern,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Execute a composable pattern.
        """
        ...
    
    @abstractmethod
    def adapt_to_domain(self, domain: str):
        """
        Adapt the agent to a specific domain.
        """
        ...
    
    @abstractmethod
    def get_available_domains(self) -> list[str]:
        """
        Get list of available domains.
        """
        ...
