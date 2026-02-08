"""
Атомарные действия для ReAct паттерна.
"""
import asyncio
import pathlib
from typing import Dict, Any, Optional
from pathlib import Path
from application.context.session_context import SessionContext
from application.orchestration.atomic_actions.base import AtomicAction
from domain.models.atomic_action.result import FileOperationActionResult, ThinkActionResult, ActActionResult, ObserveActionResult
from domain.models.atomic_action.types import AtomicActionType
from domain.abstractions.event_types import EventType


class SecurityError(Exception):
    """Исключение для безопасности атомарных действий"""
    pass


class ThinkAction(AtomicAction):
    """
    Действие мышления - анализ ситуации и формирование рассуждений
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        self.event_publisher = event_publisher

    @property
    def action_type(self) -> AtomicActionType:
        return AtomicActionType.THINK

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Проверяем наличие необходимых параметров
        required_params = ['goal']
        return all(param in parameters for param in required_params)

    async def execute(self, parameters: Dict[str, Any]) -> ThinkActionResult:
        """
        Выполнить действие мышления

        Args:
            parameters: Параметры для выполнения действия

        Returns:
            Результат рассуждения (ThinkActionResult)
        """
        goal = parameters.get('goal', "")
        history = parameters.get('history', [])
        available_capabilities = parameters.get('available_capabilities', [])

        # Простая логика рассуждения без прямого доступа к LLM
        thought = f"Анализирую текущую ситуацию для достижения цели: {goal[:50]}..."
        next_action_type = "ACT"  # По умолчанию следующий шаг - выполнение действия

        # Подготавливаем событие для публикации
        events_to_publish = [{
            "event_type": EventType.INFO,
            "source": "ThinkAction",
            "data": {
                "action": "THINK",
                "thought": thought,
                "goal": goal,
                "available_capabilities": available_capabilities
            }
        }]

        result = ThinkActionResult(
            success=True,
            action_type=AtomicActionType.THINK,
            thought=thought,
            next_action_type=next_action_type,
            context_update={
                "current_thought": thought,
                "step_type": "reasoning"
            },
            result_data={
                "thought": thought,
                "next_action_type": next_action_type
            }
        )
        result.events_to_publish = events_to_publish
        return result

    async def rollback(self, token: Optional[str]) -> ThinkActionResult:
        """Откат действия мышления"""
        return ThinkActionResult(
            success=True,
            action_type=AtomicActionType.THINK,
            thought="Откат рассуждения выполнен",
            next_action_type="THINK",
            can_rollback=False  # Рассуждение не требует отката
        )


class ActAction(AtomicAction):
    """
    Действие выполнения - выполнение конкретного действия через доступные возможности
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        self.event_publisher = event_publisher

    @property
    def action_type(self) -> AtomicActionType:
        return AtomicActionType.ACT

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Проверяем наличие необходимых параметров
        required_params = ['selected_action']
        return all(param in parameters for param in required_params)

    async def execute(self, parameters: Dict[str, Any]) -> ActActionResult:
        """
        Выполнить действие

        Args:
            parameters: Параметры для выполнения действия

        Returns:
            Результат выполнения действия (ActActionResult)
        """
        events_to_publish = []
        selected_action = parameters.get('selected_action', "")
        action_params = parameters.get('action_parameters', {})
        available_capabilities = parameters.get('available_capabilities', [])

        # Проверяем, доступна ли выбранная возможность
        if selected_action and selected_action not in available_capabilities:
            # Подготавливаем событие об ошибке
            events_to_publish.append({
                "event_type": EventType.ERROR,
                "source": "ActAction",
                "data": {
                    "action": "ACT",
                    "selected_action": selected_action,
                    "error": f"Выбранное действие '{selected_action}' недоступно",
                    "available_capabilities": available_capabilities
                }
            })

            result = ActActionResult(
                success=False,
                action_type=AtomicActionType.ACT,
                error_message=f"Выбранное действие '{selected_action}' недоступно",
                result_data={
                    "available_capabilities": available_capabilities
                }
            )
            result.events_to_publish = events_to_publish
            return result

        # В реальной реализации здесь будет выполнение выбранного действия
        result_str = f"Выполняю действие {selected_action} с параметрами {action_params}" if selected_action else "Нет действия для выполнения"

        # Подготавливаем событие о выполнении действия
        events_to_publish.append({
            "event_type": EventType.INFO,
            "source": "ActAction",
            "data": {
                "action": "ACT",
                "executed_action": selected_action,
                "action_result": result_str,
                "parameters": action_params
            }
        })

        result = ActActionResult(
            success=True,
            action_type=AtomicActionType.ACT,
            executed_action=selected_action,
            action_result=result_str,
            parameters=action_params,
            result_data={
                "executed_action": selected_action,
                "action_result": result_str,
                "parameters": action_params
            },
            context_update={
                "last_action": selected_action,
                "action_result": result_str,
                "step_type": "action"
            } if selected_action else {},
            can_rollback=True,
            rollback_token=f"act_{selected_action}_{hash(str(action_params))}"
        )
        result.events_to_publish = events_to_publish
        return result

    async def rollback(self, token: Optional[str]) -> ActActionResult:
        """Откат действия выполнения"""
        return ActActionResult(
            success=True,
            action_type=AtomicActionType.ACT,
            executed_action="ROLLBACK",
            action_result=f"Откат действия выполнен, токен: {token}",
            can_rollback=False
        )


class ObserveAction(AtomicAction):
    """
    Действие наблюдения - сбор информации о результате действия
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        self.event_publisher = event_publisher

    @property
    def action_type(self) -> AtomicActionType:
        return AtomicActionType.OBSERVE

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Проверяем наличие необходимых параметров
        required_params = ['action_result', 'last_action']
        return all(param in parameters for param in required_params)

    async def execute(self, parameters: Dict[str, Any]) -> ObserveActionResult:
        """
        Выполнить действие наблюдения

        Args:
            parameters: Параметры для выполнения действия

        Returns:
            Результат наблюдения (ObserveActionResult)
        """
        action_result = parameters.get('action_result', "")
        last_action = parameters.get('last_action', "")

        # В реальной реализации здесь будет анализ результата действия
        observation = f"Наблюдение за результатом действия '{last_action}': {action_result}"

        # Публикуем событие о наблюдении
        if self.event_publisher:
            asyncio.create_task(
                self.event_publisher.publish(
                    EventType.INFO,
                    "ObserveAction",
                    {
                        "action": "OBSERVE",
                        "last_action": last_action,
                        "action_result": action_result,
                        "observation": observation
                    }
                )
            )

        return ObserveActionResult(
            success=True,
            action_type=AtomicActionType.OBSERVE,
            observation=observation,
            processed_result=action_result,
            result_data={
                "observation": observation,
                "processed_result": action_result
            },
            context_update={
                "current_observation": observation,
                "step_type": "observation"
            }
        )

    async def rollback(self, token: Optional[str]) -> ObserveActionResult:
        """Откат действия наблюдения"""
        return ObserveActionResult(
            success=True,
            action_type=AtomicActionType.OBSERVE,
            observation="Откат наблюдения выполнен",
            processed_result="",
            can_rollback=False  # Наблюдение не требует отката
        )


