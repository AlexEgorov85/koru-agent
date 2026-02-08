# Базовый класс для атомарных действий
"""
AtomicAction — базовый класс, реализующий IAtomicAction интерфейс
"""

from abc import ABC
from typing import Dict, Any, Optional
from domain.abstractions.atomic_action import IAtomicAction
from domain.models.atomic_action.result import AtomicActionResult
from domain.models.atomic_action.types import AtomicActionType


class AtomicAction(IAtomicAction, ABC):
    """
    Базовый класс для атомарных действий, реализующий IAtomicAction интерфейс
    """
    
    @property
    def action_type(self) -> AtomicActionType:
        """Тип атомарного действия - должен быть переопределен в наследниках"""
        raise NotImplementedError("Каждый наследник должен реализовать свойство action_type")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """По умолчанию параметры считаются валидными"""
        return True
    
    async def rollback(self, token: Optional[str]) -> AtomicActionResult:
        """По умолчанию откат не поддерживается"""
        return AtomicActionResult(
            success=False,
            action_type=self.action_type,
            error_message="Rollback not implemented for this action",
            can_rollback=False
        )