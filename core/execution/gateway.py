"""
Шлюз выполнения - единая точка выполнения действий агента.

СОДЕРЖИТ:
- Управление выполнением действий
- Интеграцию с инфраструктурными сервисами
- Обработку результатов выполнения
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.application.context.application_context import ApplicationContext
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus


class ExecutionGateway:
    """Шлюз выполнения - единая точка выполнения действий агента."""

    def __init__(self, application_context: ApplicationContext):
        """
        Инициализация шлюза выполнения.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст агента
        """
        self.application_context = application_context
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def execute(self, action: Dict[str, Any]) -> ExecutionResult:
        """
        Выполнение действия через шлюз.

        ПАРАМЕТРЫ:
        - action: Описание действия для выполнения

        ВОЗВРАЩАЕТ:
        - ExecutionResult: Результат выполнения действия
        """
        start_time = datetime.now()

        try:
            action_type = action.get("action_type", "unknown")
            self.logger.debug(f"Выполнение действия: {action_type}")

            if action_type == "execute_skill":
                result = await self._execute_skill(action)
            elif action_type == "execute_tool":
                result = await self._execute_tool(action)
            elif action_type == "get_context":
                result = await self._get_context(action)
            elif action_type == "continue":
                result = ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result={"message": "Продолжение выполнения", "action": action},
                    steps_executed=0,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    metadata={"action_type": action_type}
                )
            elif action_type == "final_answer":
                result = ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    result=action.get("result", {}),
                    steps_executed=0,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    metadata={"action_type": action_type}
                )
            else:
                result = ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    result={"error": f"Неизвестный тип действия: {action_type}", "action": action},
                    steps_executed=0,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    metadata={"action_type": action_type}
                )

            return result

        except Exception as e:
            self.logger.error(f"Ошибка выполнения действия: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": str(e), "action": action},
                steps_executed=0,
                execution_time=(datetime.now() - start_time).total_seconds(),
                metadata={"action_type": action.get("action_type", "unknown"), "exception": str(e)}
            )

    async def _execute_skill(self, action: Dict[str, Any]) -> ExecutionResult:
        """Выполнение навыка."""
        skill_name = action.get("skill_name", "")
        parameters = action.get("parameters", {})
        capability_name = action.get("capability", "")

        # Получение навыка из прикладного контекста
        skill = self.application_context.get_skill(skill_name)
        if not skill:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": f"Навык не найден: {skill_name}"},
                steps_executed=0,
                execution_time=0,
                metadata={"action_type": "execute_skill", "skill_name": skill_name}
            )

        try:
            # Выполнение навыка
            result = await skill.execute(
                capability=None,  # В реальной системе здесь будет объект capability
                parameters=parameters,
                context=self.application_context
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                steps_executed=1,
                execution_time=0,  # В реальной системе здесь будет точное время
                metadata={
                    "action_type": "execute_skill",
                    "skill_name": skill_name,
                    "capability": capability_name
                }
            )
        except Exception as e:
            self.logger.error(f"Ошибка выполнения навыка {skill_name}: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": str(e), "skill_name": skill_name},
                steps_executed=0,
                execution_time=0,
                metadata={
                    "action_type": "execute_skill",
                    "skill_name": skill_name,
                    "capability": capability_name,
                    "exception": str(e)
                }
            )

    async def _execute_tool(self, action: Dict[str, Any]) -> ExecutionResult:
        """Выполнение инструмента."""
        tool_name = action.get("tool_name", "")
        parameters = action.get("parameters", {})

        # Получение инструмента из прикладного контекста
        tool = self.application_context.get_tool(tool_name)
        if not tool:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": f"Инструмент не найден: {tool_name}"},
                steps_executed=0,
                execution_time=0,
                metadata={"action_type": "execute_tool", "tool_name": tool_name}
            )

        try:
            # Выполнение инструмента
            result = await tool.execute(
                capability=None,  # В реальной системе здесь будет объект capability
                parameters=parameters,
                context=self.application_context
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                steps_executed=1,
                execution_time=0,  # В реальной системе здесь будет точное время
                metadata={
                    "action_type": "execute_tool",
                    "tool_name": tool_name
                }
            )
        except Exception as e:
            self.logger.error(f"Ошибка выполнения инструмента {tool_name}: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": str(e), "tool_name": tool_name},
                steps_executed=0,
                execution_time=0,
                metadata={
                    "action_type": "execute_tool",
                    "tool_name": tool_name,
                    "exception": str(e)
                }
            )

    async def _get_context(self, action: Dict[str, Any]) -> ExecutionResult:
        """Получение контекста."""
        context_type = action.get("context_type", "general")
        
        try:
            if context_type == "data":
                result = self.application_context.data_context.get_current_state() if self.application_context.data_context else {}
            elif context_type == "step":
                result = self.application_context.step_context.get_current_state() if self.application_context.step_context else {}
            else:
                result = {
                    "data_context": self.application_context.data_context.get_current_state() if self.application_context.data_context else {},
                    "step_context": self.application_context.step_context.get_current_state() if self.application_context.step_context else {},
                    "agent_config": self.application_context.agent_config
                }

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                steps_executed=0,
                execution_time=0,
                metadata={
                    "action_type": "get_context",
                    "context_type": context_type
                }
            )
        except Exception as e:
            self.logger.error(f"Ошибка получения контекста {context_type}: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": str(e), "context_type": context_type},
                steps_executed=0,
                execution_time=0,
                metadata={
                    "action_type": "get_context",
                    "context_type": context_type,
                    "exception": str(e)
                }
            )