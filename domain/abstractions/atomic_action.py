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
    def name(self) -> str:
        """Название действия"""
        pass
    
    @abstractmethod
    def requires_confirmation(self) -> bool:
        """Требуется ли подтверждение для выполнения действия"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Валидация параметров действия"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> AtomicActionResult:
        """Выполнение атомарного действия"""
        pass
    
    @abstractmethod
    async def rollback(self, token: Optional[str]) -> AtomicActionResult:
        """Откат выполненного действия"""
        pass
    
    @property
    @abstractmethod
    def action_type(self) -> AtomicActionType:
        """Тип атомарного действия"""
        pass