"""
Абстракции для атомарных действий
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.models.atomic_action.result import AtomicActionResult
from domain.models.atomic_action.types import AtomicActionType


class IAtomicAction(ABC):
    """
    Интерфейс для атомарного действия
    """
    
    @property
    @abstractmethod
    def action_type(self) -> AtomicActionType:
        """Тип атомарного действия"""
        pass

    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> AtomicActionResult:
        """
        Выполнить атомарное действие

        Args:
            parameters: Параметры для выполнения действия

        Returns:
            Результат выполнения действия
        """
        pass

    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Валидация параметров действия

        Args:
            parameters: Параметры для валидации

        Returns:
            True если параметры валидны, иначе False
        """
        pass

    @abstractmethod
    async def rollback(self, token: Optional[str]) -> AtomicActionResult:
        """
        Откат выполненного действия

        Args:
            token: Токен для выполнения отката

        Returns:
            Результат выполнения отката
        """
        pass