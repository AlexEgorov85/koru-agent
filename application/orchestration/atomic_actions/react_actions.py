"""
Атомарные действия для ReAct паттерна.
"""
import asyncio
from typing import Dict, Any, Optional
from application.orchestration.atomic_actions.base import AtomicAction
from application.orchestration.atomic_actions.models import ThinkActionResult, ActActionResult, ObserveActionResult
from application.context.session.session_context import SessionContext
from domain.abstractions.event_types import EventType


class ThinkAction(AtomicAction):
    """
    Действие мышления - анализ ситуации и формирование рассуждений
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        super().__init__(event_publisher=event_publisher)

    def execute(self, context: SessionContext) -> ThinkActionResult:
        """
        Выполнить действие мышления

        Args:
            context: Контекст выполнения (SessionContext), содержащий цель, текущую информацию и т.д.

        Returns:
            Результат рассуждения (ThinkActionResult)
        """
        goal = getattr(context, 'goal', "") or ""
        history = getattr(context, 'history', []) or []
        available_capabilities = getattr(context, 'available_capabilities', []) or []

        # Простая логика рассуждения без прямого доступа к LLM
        thought = f"Анализирую текущую ситуацию для достижения цели: {goal[:50]}..."
        next_action_type = "ACT"  # По умолчанию следующий шаг - выполнение действия

        # Публикуем событие о начале рассуждения
        if self.event_publisher:
            asyncio.create_task(
                self._publish_event(
                    EventType.INFO,
                    "ThinkAction",
                    {
                        "action": "THINK",
                        "thought": thought,
                        "goal": goal,
                        "available_capabilities": available_capabilities
                    }
                )
            )

        return ThinkActionResult(
            success=True,
            action_type="THINK",
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


class ActAction(AtomicAction):
    """
    Действие выполнения - выполнение конкретного действия через доступные возможности
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        super().__init__(event_publisher=event_publisher)

    def execute(self, context: SessionContext) -> ActActionResult:
        """
        Выполнить действие

        Args:
            context: Контекст выполнения (SessionContext), содержащий выбранное действие и параметры

        Returns:
            Результат выполнения действия (ActActionResult)
        """
        selected_action = getattr(context, 'selected_action', "") or ""
        action_params = getattr(context, 'action_parameters', {}) or {}
        available_capabilities = getattr(context, 'available_capabilities', []) or []

        # Проверяем, доступна ли выбранная возможность
        if selected_action and selected_action not in available_capabilities:
            # Публикуем событие об ошибке
            if self.event_publisher:
                asyncio.create_task(
                    self._publish_event(
                        EventType.ERROR,
                        "ActAction",
                        {
                            "action": "ACT",
                            "selected_action": selected_action,
                            "error": f"Выбранное действие '{selected_action}' недоступно",
                            "available_capabilities": available_capabilities
                        }
                    )
                )

            return ActActionResult(
                success=False,
                action_type="ACT",
                error_message=f"Выбранное действие '{selected_action}' недоступно",
                result_data={
                    "available_capabilities": available_capabilities
                }
            )

        # В реальной реализации здесь будет выполнение выбранного действия
        result = f"Выполняю действие {selected_action} с параметрами {action_params}" if selected_action else "Нет действия для выполнения"

        # Публикуем событие о выполнении действия
        if self.event_publisher:
            asyncio.create_task(
                self._publish_event(
                    EventType.INFO,
                    "ActAction",
                    {
                        "action": "ACT",
                        "executed_action": selected_action,
                        "action_result": result,
                        "parameters": action_params
                    }
                )
            )

        return ActActionResult(
            success=True,
            action_type="ACT",
            executed_action=selected_action,
            action_result=result,
            parameters=action_params,
            result_data={
                "executed_action": selected_action,
                "action_result": result,
                "parameters": action_params
            },
            context_update={
                "last_action": selected_action,
                "action_result": result,
                "step_type": "action"
            } if selected_action else {}
        )


class ObserveAction(AtomicAction):
    """
    Действие наблюдения - сбор информации о результате действия
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        super().__init__(event_publisher=event_publisher)

    def execute(self, context: SessionContext) -> ObserveActionResult:
        """
        Выполнить действие наблюдения

        Args:
            context: Контекст выполнения (SessionContext), содержащий результаты предыдущих действий

        Returns:
            Результат наблюдения (ObserveActionResult)
        """
        action_result = getattr(context, 'action_result', "") or ""
        last_action = getattr(context, 'last_action', "") or ""

        # В реальной реализации здесь будет анализ результата действия
        observation = f"Наблюдение за результатом действия '{last_action}': {action_result}"

        # Публикуем событие о наблюдении
        if self.event_publisher:
            asyncio.create_task(
                self._publish_event(
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
            action_type="OBSERVE",
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


class FileOperationAction(AtomicAction):
    """
    Действие операции с файлами - чтение, запись, удаление, список файлов
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        super().__init__(event_publisher=event_publisher)

    def execute(self, context: SessionContext) -> FileOperationActionResult:
        """
        Выполнить файловую операцию

        Args:
            context: Контекст выполнения (SessionContext), содержащий тип операции и параметры

        Returns:
            Результат файловой операции
        """
        operation_type = getattr(context, 'file_operation_type', "") or ""
        file_path = getattr(context, 'file_path', "") or ""
        file_content = getattr(context, 'file_content', "") or ""
        file_mode = getattr(context, 'file_mode', "r") or "r"

        # Проверяем тип операции
        if operation_type not in ["read", "write", "delete", "list", "exists"]:
            # Публикуем событие об ошибке
            if self.event_publisher:
                asyncio.create_task(
                    self._publish_event(
                        EventType.ERROR,
                        "FileOperationAction",
                        {
                            "action": "FILE_OPERATION",
                            "operation_type": operation_type,
                            "error": f"Неподдерживаемый тип файловой операции: {operation_type}",
                            "file_path": file_path
                        }
                    )
                )

            return FileOperationActionResult(
                success=False,
                action_type="FILE_OPERATION",
                error_message=f"Неподдерживаемый тип файловой операции: {operation_type}",
                operation_type=operation_type,
                file_path=file_path,
                result_data={
                    "supported_operations": ["read", "write", "delete", "list", "exists"]
                }
            )

        # Выполняем операцию в зависимости от типа
        result = None
        success = False

        try:
            if operation_type == "read":
                # Логика чтения файла
                result = f"Содержимое файла {file_path} прочитано"
                success = True
            elif operation_type == "write":
                # Логика записи файла
                result = f"Файл {file_path} записан с содержимым длиной {len(file_content)} символов"
                success = True
            elif operation_type == "delete":
                # Логика удаления файла
                result = f"Файл {file_path} удален"
                success = True
            elif operation_type == "list":
                # Логика получения списка файлов
                result = f"Список файлов в директории {file_path} получен"
                success = True
            elif operation_type == "exists":
                # Логика проверки существования файла
                result = f"Файл {file_path} существует: True"
                success = True

            # Публикуем событие о выполнении файловой операции
            if self.event_publisher:
                asyncio.create_task(
                    self._publish_event(
                        EventType.INFO,
                        "FileOperationAction",
                        {
                            "action": "FILE_OPERATION",
                            "operation_type": operation_type,
                            "file_path": file_path,
                            "result": result,
                            "success": success
                        }
                    )
                )

            return FileOperationActionResult(
                success=success,
                action_type="FILE_OPERATION",
                operation_type=operation_type,
                file_path=file_path,
                result=result,
                result_data={
                    "operation_type": operation_type,
                    "file_path": file_path,
                    "result": result
                },
                context_update={
                    "last_file_operation": operation_type,
                    "last_file_path": file_path,
                    "step_type": "file_operation"
                }
            )

        except Exception as e:
            # Публикуем событие об ошибке
            if self.event_publisher:
                asyncio.create_task(
                    self._publish_event(
                        EventType.ERROR,
                        "FileOperationAction",
                        {
                            "action": "FILE_OPERATION",
                            "operation_type": operation_type,
                            "file_path": file_path,
                            "error": str(e)
                        }
                    )
                )

            return FileOperationActionResult(
                success=False,
                action_type="FILE_OPERATION",
                operation_type=operation_type,
                file_path=file_path,
                error_message=str(e),
                result_data={
                    "operation_type": operation_type,
                    "file_path": file_path,
                    "error": str(e)
                }
            )