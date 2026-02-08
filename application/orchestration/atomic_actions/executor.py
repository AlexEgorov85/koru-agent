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
    
    async def execute(
        self,
        action_type: AtomicActionType,
        parameters: Dict[str, Any],
        timeout: float = 30.0
    ) -> AtomicActionResult:
        """Выполнение одного атомарного действия с таймаутом"""
        events_to_publish = []
        
        action = self.get_action(action_type)
        if not action:
            error_msg = f"Атомарное действие '{action_type}' не найдено"
            events_to_publish.append({
                "event_type": EventType.ERROR,
                "source": "AtomicActionExecutor",
                "data": {"error": error_msg}
            })
            result = AtomicActionResult(
                success=False,
                action_type=action_type,
                error_message=error_msg,
                error_type="ACTION_NOT_FOUND"
            )
            result.events_to_publish = events_to_publish
            return result

        # Валидация параметров
        if not action.validate_parameters(parameters):
            error_msg = f"Неверные параметры для действия '{action_type}'"
            events_to_publish.append({
                "event_type": EventType.ERROR,
                "source": "AtomicActionExecutor",
                "data": {"error": error_msg, "parameters": parameters}
            })
            result = AtomicActionResult(
                success=False,
                action_type=action_type,
                error_message=error_msg,
                error_type="PARAMETER_VALIDATION_ERROR"
            )
            result.events_to_publish = events_to_publish
            return result

        try:
            # Выполнение с таймаутом
            start_time = asyncio.get_event_loop().time()
            result = await asyncio.wait_for(action.execute(parameters), timeout=timeout)
            execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            result.execution_time_ms = execution_time

            # Добавляем результат в стек отката, если поддерживается
            if result.can_rollback and result.rollback_token:
                self._rollback_stack.append((action_type, result.rollback_token))

            # Добавляем событие об успешном выполнении
            events_to_publish.append({
                "event_type": EventType.INFO,
                "source": "AtomicActionExecutor",
                "data": {
                    "message": f"Атомарное действие '{action_type}' выполнено успешно",
                    "action_type": action_type,
                    "execution_time_ms": execution_time
                }
            })
            result.events_to_publish = events_to_publish
            return result
        except asyncio.TimeoutError:
            error_msg = f"Таймаут выполнения действия '{action_type}' ({timeout}s)"
            events_to_publish.append({
                "event_type": EventType.ERROR,
                "source": "AtomicActionExecutor",
                "data": {"error": error_msg}
            })
            result = AtomicActionResult(
                success=False,
                action_type=action_type,
                error_message=error_msg,
                error_type="TIMEOUT_ERROR"
            )
            result.events_to_publish = events_to_publish
            return result
        except Exception as e:
            error_msg = f"Ошибка выполнения действия '{action_type}': {str(e)}"
            events_to_publish.append({
                "event_type": EventType.ERROR,
                "source": "AtomicActionExecutor",
                "data": {"error": error_msg}
            })
            result = AtomicActionResult(
                success=False,
                action_type=action_type,
                error_message=error_msg,
                error_type="EXECUTION_ERROR"
            )
            result.events_to_publish = events_to_publish
            return result
    
    async def execute_sequence(
        self,
        sequence: List[Dict[str, Any]],
        timeout_per_action: int = 30,
        rollback_on_failure: bool = True
    ) -> List[AtomicActionResult]:
        """Выполнение последовательности действий с автоматическим откатом"""
        results = []
        successful_count = 0
        
        for step, action_def in enumerate(sequence):
            action_type_str = action_def.get("action_type")
            if not action_type_str:
                error_msg = f"Не указан тип действия на шаге {step}"
                result = AtomicActionResult(
                    success=False,
                    action_type=AtomicActionType.THINK,  # Заглушка
                    error_message=error_msg,
                    error_type="MISSING_ACTION_TYPE"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            # Преобразуем строку в AtomicActionType
            try:
                action_type = AtomicActionType(action_type_str)
            except ValueError:
                error_msg = f"Некорректный тип действия: {action_type_str}"
                result = AtomicActionResult(
                    success=False,
                    action_type=AtomicActionType.THINK,  # Заглушка
                    error_message=error_msg,
                    error_type="INVALID_ACTION_TYPE"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            parameters = action_def.get("parameters", {})
            
            action = self.get_action(action_type)
            if action is None:
                error_msg = f"Атомарное действие '{action_type}' не зарегистрировано"
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message=error_msg,
                    error_type="ACTION_NOT_REGISTERED"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            # Валидация параметров
            if not action.validate_parameters(parameters):
                error_msg = "Некорректные параметры для действия"
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message=error_msg,
                    error_type="PARAMETER_VALIDATION_ERROR"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
            
            # Выполнение с таймаутом
            try:
                start_time = asyncio.get_event_loop().time()
                result = await asyncio.wait_for(
                    action.execute(parameters),
                    timeout=timeout_per_action
                )
                execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
                result.execution_time_ms = execution_time
                
                results.append(result)
                
                if result.success:
                    successful_count += 1
                else:
                    # Если произошла ошибка и включена опция отката
                    if rollback_on_failure and result.can_rollback and result.rollback_token:
                        # Откатываем все предыдущие успешные действия в обратном порядке
                        await self._perform_rollback_up_to(successful_count)
                    
                    # Прервать выполнение при ошибке
                    break
                    
            except asyncio.TimeoutError:
                error_msg = f"Таймаут ({timeout_per_action}s)"
                result = AtomicActionResult(
                    success=False,
                    action_type=action_type,
                    error_message=error_msg,
                    error_type="TIMEOUT_ERROR"
                )
                results.append(result)
                if rollback_on_failure:
                    await self._perform_rollback()
                break
        
        return results
    
    async def _perform_rollback_up_to(self, successful_count: int):
        """Выполнение отката для указанного количества успешных действий"""
        # Откатываем последние successful_count действий в обратном порядке
        for _ in range(successful_count):
            if self._rollback_stack:
                action_type, rollback_token = self._rollback_stack.pop()
                action = self.get_action(action_type)
                if action:
                    try:
                        rollback_result = await action.rollback(rollback_token)
                        if self.event_publisher:
                            await self.event_publisher.publish(
                                EventType.INFO,
                                "AtomicActionExecutor",
                                {
                                    "action": "ROLLBACK",
                                    "action_type": action_type,
                                    "rollback_token": rollback_token,
                                    "success": rollback_result.success
                                }
                            )
                    except Exception as e:
                        if self.event_publisher:
                            await self.event_publisher.publish(
                                EventType.ERROR,
                                "AtomicActionExecutor",
                                {
                                    "action": "ROLLBACK",
                                    "action_type": action_type,
                                    "rollback_token": rollback_token,
                                    "error": str(e)
                                }
                            )
    
    async def _perform_rollback(self):
        """Выполнение полного отката всех зарегистрированных действий в обратном порядке"""
        while self._rollback_stack:
            action_type, rollback_token = self._rollback_stack.pop()
            action = self.get_action(action_type)
            if action:
                try:
                    rollback_result = await action.rollback(rollback_token)
                    if self.event_publisher:
                        await self.event_publisher.publish(
                            EventType.INFO,
                            "AtomicActionExecutor",
                            {
                                "action": "FULL_ROLLBACK",
                                "action_type": action_type,
                                "rollback_token": rollback_token,
                                "success": rollback_result.success
                            }
                        )
                except Exception as e:
                    if self.event_publisher:
                        await self.event_publisher.publish(
                            EventType.ERROR,
                            "AtomicActionExecutor",
                            {
                                "action": "FULL_ROLLBACK",
                                "action_type": action_type,
                                "rollback_token": rollback_token,
                                "error": str(e)
                            }
                        )