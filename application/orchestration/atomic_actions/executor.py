"""
Исполнитель атомарных действий
"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from domain.abstractions.atomic_action import IAtomicAction
from domain.abstractions.event_types import IEventPublisher, EventType
from domain.models.atomic_action.result import AtomicActionResult
from domain.models.atomic_action.types import AtomicActionType


class AtomicActionExecutor:
    """
    Исполнитель атомарных действий с поддержкой композиции и отката
    """
    
    def __init__(self, event_publisher: Optional[IEventPublisher] = None):
        self.actions: Dict[AtomicActionType, IAtomicAction] = {}
        self.event_publisher = event_publisher
        self._rollback_stack: List[tuple] = []  # (action_type, rollback_token)
    
    def register_action(self, action: IAtomicAction):
        """Регистрация атомарного действия"""
        self.actions[action.action_type] = action
    
    def get_action(self, action_type: AtomicActionType) -> Optional[IAtomicAction]:
        """Получение зарегистрированного действия"""
        return self.actions.get(action_type)
    
    async def execute_sequence(
        self,
        sequence: List[Dict[str, Any]],
        timeout_per_action: int = 30,
        rollback_on_failure: bool = True
    ) -> List[AtomicActionResult]:
        """Выполнение последовательности действий с автоматическим откатом"""
        results = []
        
        for step, action_def in enumerate(sequence):
            action_type = AtomicActionType(action_def["action_type"])
            action = self.get_action(action_type)
            
            if action is None:
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message="Действие не зарегистрировано",
                    error_type="ACTION_NOT_FOUND"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            # Валидация параметров
            if not action.validate_parameters(action_def.get("parameters", {})):
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message="Некорректные параметры",
                    error_type="VALIDATION_ERROR"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            # Выполнение с таймаутом
            try:
                start_time = asyncio.get_event_loop().time()
                result = await asyncio.wait_for(
                    action.execute(action_def.get("parameters", {})),
                    timeout=timeout_per_action
                )
                execution_time = int(
                    (asyncio.get_event_loop().time() - start_time) * 1000
                )
                result.execution_time_ms = execution_time
                
                results.append(result)
                
                # Сохранить токен отката при необходимости
                if result.can_rollback and result.rollback_token:
                    self._rollback_stack.append((action_type, result.rollback_token))
                
                # Прервать при критической ошибке
                if not result.success and result.error_type in [
                    "SECURITY_VIOLATION", "ACTION_NOT_FOUND"
                ]:
                    if rollback_on_failure:
                        await self._perform_rollback()
                    break
                    
            except asyncio.TimeoutError:
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message=f"Таймаут ({timeout_per_action}s)",
                    error_type="TIMEOUT_ERROR"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
        
        return results
    
    async def _perform_rollback(self):
        """Выполнение отката в обратном порядке"""
        while self._rollback_stack:
            action_type, rollback_token = self._rollback_stack.pop()
            action = self.get_action(action_type)
            if action:
                await action.rollback(rollback_token)