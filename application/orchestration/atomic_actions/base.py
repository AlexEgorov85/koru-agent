# Базовый класс для атомарных действий
"""
AtomicAction — базовый класс, реализующий IAtomicAction интерфейс
"""

from abc import ABC
from typing import Dict, Any, Optional
from domain.abstractions.atomic_action import IAtomicAction
from domain.models.atomic_action.result import AtomicActionResult


class AtomicAction(IAtomicAction, ABC):
    """
    Базовый класс для атомарных действий, реализующий IAtomicAction интерфейс
    """
    
    @property
    def name(self) -> str:
        """Название действия по умолчанию - имя класса"""
        return self.__class__.__name__
    
    def requires_confirmation(self) -> bool:
        """По умолчанию действия не требуют подтверждения"""
        return False
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """По умолчанию параметры считаются валидными"""
        return True
    
    async def rollback(self, token: Optional[str]) -> AtomicActionResult:
        """По умолчанию откат не поддерживается"""
        from domain.models.atomic_action.result import AtomicActionResult
        from domain.models.atomic_action.types import AtomicActionType
        
        return AtomicActionResult(
            success=False,
            action_type=AtomicActionType.THINK,  # Placeholder type
            error_message="Rollback not implemented for this action",
            can_rollback=False
        )