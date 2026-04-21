"""
Хендлер выполнения действия через SafeExecutor.
"""
from typing import Optional, TYPE_CHECKING

from core.agent.runtime.handlers.base import IStepHandler
from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.behaviors.base import DecisionType
from core.agent.components.action_executor import ExecutionContext

if TYPE_CHECKING:
    from core.agent.components.safe_executor import SafeExecutor


class ActionHandler(IStepHandler):
    """
    Хендлер для выполнения действия через SafeExecutor.
    
    Выполняет действие и возвращает ExecutionResult.
    """
    
    def __init__(
        self,
        safe_executor: "SafeExecutor",
        event_bus,
        session_id: str,
        agent_id: str,
        log,
    ):
        self.safe_executor = safe_executor
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self.log = log
    
    async def execute(self, context: SessionContext) -> Optional[ExecutionResult]:
        """
        Выполнить действие через SafeExecutor.
        
        Returns:
            ExecutionResult с результатом выполнения
        """
        # Получаем решение из контекста
        decision = getattr(context.step_context, "_current_decision", None)
        
        if decision is None or decision.type != DecisionType.ACT:
            # Нет решения или это не ACT — пропускаем выполнение
            return None
        
        action_name = decision.action or ""
        parameters = decision.parameters or {}
        
        # Логируем начало выполнения
        self.log.info(
            f"⚙️ Запускаю {action_name} с параметрами: {parameters}",
            extra={"event_type": "TOOL_CALL"},
        )
        
        # Публикуем событие выбора capability
        await self.event_bus.publish(
            "CAPABILITY_SELECTED",
            {
                "capability": action_name,
                "pattern": decision.type.value,
                "reasoning": decision.reasoning or "",
                "step": context.step_context.count() + 1,
            },
            session_id=self.session_id,
            agent_id=self.agent_id,
        )
        
        # Выполняем действие
        try:
            result = await self.safe_executor.execute(
                capability_name=action_name,
                parameters=parameters,
                context=ExecutionContext(
                    session_context=context,
                    session_id=self.session_id,
                    agent_id=self.agent_id,
                ),
            )
            
            # Логируем результат
            if result.status == ExecutionStatus.FAILED:
                self.log.error(
                    f"❌ Действие {action_name} завершилось с ошибкой: {result.error or 'неизвестная'}",
                    extra={"event_type": "TOOL_ERROR"},
                )
            else:
                self.log.info(
                    f"✅ Действие {action_name} выполнено",
                    extra={"event_type": "TOOL_RESULT"},
                )
                
        except Exception as e:
            self.log.error(
                f"❌ Исключение при выполнении {action_name}: {e}",
                extra={"event_type": "TOOL_ERROR"},
                exc_info=True,
            )
            result = ExecutionResult.failure(str(e))
        
        # Публикуем событие выполнения
        await self.event_bus.publish(
            "ACTION_PERFORMED",
            {
                "action": action_name,
                "parameters": parameters,
                "status": result.status.value,
                "error": result.error,
                "step": context.step_context.count() + 1,
            },
            session_id=self.session_id,
            agent_id=self.agent_id,
        )
        
        # Сохраняем результат в контексте для пост-обработки рекордером
        context.step_context._last_execution_result = result
        
        return result
