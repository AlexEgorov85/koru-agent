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
from core.infrastructure.event_bus.event_bus import EventType


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

    async def execute_capability(
        self,
        capability,
        action_payload: dict,
        session,
        step_number: int,
        user_context=None
    ) -> ExecutionResult:
        """
        Выполнение capability через шлюз.

        ПАРАМЕТРЫ:
        - capability: Объект способности для выполнения
        - action_payload: Параметры для выполнения
        - session: Контекст сессии
        - step_number: Номер шага
        - user_context: Контекст пользователя

        ВОЗВРАЩАЕТ:
        - ExecutionResult: Результат выполнения
        """
        start_time = datetime.now()
        capability_name = getattr(capability, 'name', 'unknown')

        try:
            self.logger.info(f"=== ВЫПОЛНЕНИЕ CAPABILITY ===")
            self.logger.info(f"capability_name: {capability_name}")
            self.logger.info(f"step_number: {step_number}")

            # Публикация события выбора способности
            event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                await event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    data={
                        "capability": capability_name,
                        "reasoning": action_payload.get("reasoning", "Выполнение capability"),
                        "session_id": getattr(session, 'session_id', 'unknown'),
                        "agent_id": getattr(session, 'agent_id', 'unknown'),
                        "step_number": step_number
                    },
                    source="ExecutionGateway"
                )

            # Выполнение capability
            result = await capability.execute(
                capability=capability,
                parameters=action_payload,
                context=self.application_context
            )

            self.logger.info(f"✅ Capability выполнена успешно")

            # Публикация события выполнения
            if event_bus:
                await event_bus.publish(
                    EventType.SKILL_EXECUTED,
                    data={
                        "capability": capability_name,
                        "result": str(result),
                        "session_id": getattr(session, 'session_id', 'unknown'),
                        "agent_id": getattr(session, 'agent_id', 'unknown'),
                        "step_number": step_number
                    },
                    source="ExecutionGateway"
                )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result,
                steps_executed=1,
                execution_time=(datetime.now() - start_time).total_seconds(),
                metadata={
                    "capability": capability_name,
                    "step_number": step_number
                }
            )

        except Exception as e:
            self.logger.error(f"❌ Ошибка выполнения capability {capability_name}: {str(e)}", exc_info=True)
            
            # Публикация события об ошибке
            if event_bus:
                from core.infrastructure.event_bus.event_bus import EventType as ErrorEventType
                await event_bus.publish(
                    ErrorEventType.ERROR_OCCURRED,
                    data={
                        "capability": capability_name,
                        "error": str(e),
                        "error_type": "capability_execution_error",
                        "session_id": getattr(session, 'session_id', 'unknown'),
                        "step_number": step_number
                    },
                    source="ExecutionGateway"
                )
            
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": str(e)},
                steps_executed=0,
                execution_time=(datetime.now() - start_time).total_seconds(),
                metadata={
                    "capability": capability_name,
                    "step_number": step_number,
                    "exception": str(e)
                }
            )

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

        self.logger.info(f"=== ВЫПОЛНЕНИЕ НАВЫКА ===")
        self.logger.info(f"skill_name: {skill_name}")
        self.logger.info(f"capability: {capability_name}")
        self.logger.info(f"parameters: {parameters}")

        # Получение навыка из прикладного контекста
        skill = self.application_context.get_skill(skill_name)
        if not skill:
            self.logger.error(f"Навык не найден: {skill_name}")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                result={"error": f"Навык не найден: {skill_name}"},
                steps_executed=0,
                execution_time=0,
                metadata={"action_type": "execute_skill", "skill_name": skill_name}
            )

        try:
            # Публикация события выбора способности
            event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                session_context = getattr(self.application_context, 'session_context', None)
                await event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    data={
                        "capability": capability_name,
                        "skill_name": skill_name,
                        "reasoning": parameters.get("reasoning", "Выполнение навыка"),
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "agent_id": getattr(session_context, 'agent_id', 'unknown'),
                        "step_number": getattr(session_context, 'current_step', 0) + 1
                    },
                    source="ExecutionGateway"
                )

            # Выполнение навыка
            self.logger.info(f"Вызов skill.execute()...")
            result = await skill.execute(
                capability=None,  # В реальной системе здесь будет объект capability
                parameters=parameters,
                context=self.application_context
            )

            self.logger.info(f"✅ Навык выполнен успешно")
            self.logger.info(f"result: {result}")

            # Публикация события выполнения навыка
            if event_bus:
                await event_bus.publish(
                    EventType.SKILL_EXECUTED,
                    data={
                        "capability": capability_name,
                        "skill_name": skill_name,
                        "result": str(result),
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "agent_id": getattr(session_context, 'agent_id', 'unknown'),
                        "step_number": getattr(session_context, 'current_step', 0) + 1
                    },
                    source="ExecutionGateway"
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
            self.logger.error(f"❌ Ошибка выполнения навыка {skill_name}: {str(e)}", exc_info=True)
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
            # Публикация события выбора способности
            event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                session_context = getattr(self.application_context, 'session_context', None)
                await event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    data={
                        "capability": tool_name,
                        "tool_name": tool_name,
                        "reasoning": parameters.get("reasoning", "Выполнение инструмента"),
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "agent_id": getattr(session_context, 'agent_id', 'unknown'),
                        "step_number": getattr(session_context, 'current_step', 0) + 1
                    },
                    source="ExecutionGateway"
                )

            # Выполнение инструмента
            result = await tool.execute(
                capability=None,  # В реальной системе здесь будет объект capability
                parameters=parameters,
                context=self.application_context
            )

            # Публикация события выполнения инструмента
            if event_bus:
                await event_bus.publish(
                    EventType.SKILL_EXECUTED,
                    data={
                        "capability": tool_name,
                        "tool_name": tool_name,
                        "result": str(result),
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "agent_id": getattr(session_context, 'agent_id', 'unknown'),
                        "step_number": getattr(session_context, 'current_step', 0) + 1
                    },
                    source="ExecutionGateway"
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