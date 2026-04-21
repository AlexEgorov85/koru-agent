"""
Хендлер проверки политики перед выполнением действия.
"""
from typing import Optional

from core.agent.runtime.handlers.base import IStepHandler
from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.behaviors.base import DecisionType, Decision


class PolicyCheckHandler(IStepHandler):
    """
    Хендлер для проверки AgentPolicy перед выполнением действия.
    
    Если политика запрещает действие, регистрирует шаг как blocked
    и продолжает конвейер (следующая итерация цикла получит новое решение).
    """
    
    def __init__(self, policy):
        self.policy = policy
    
    async def execute(self, context: SessionContext) -> Optional[ExecutionResult]:
        """
        Проверить политику для текущего решения.
        
        Returns:
            None всегда — политика не завершает цикл, только пропускает шаги
        """
        # Получаем решение из контекста
        decision = getattr(context.step_context, "_current_decision", None)
        
        if decision is None or decision.type != DecisionType.ACT:
            # Нет решения или это не ACT — пропускаем проверку
            return None
        
        action_name = decision.action or ""
        parameters = decision.parameters or {}
        
        # Проверяем политику
        policy_allowed, policy_reason = self.policy.check_step(
            action_name,
            parameters,
            context.agent_state,
        )
        
        if not policy_allowed:
            # Политика заблокировала действие
            context.agent_state.errors.append(f"POLICY:{policy_reason}")
            
            # Регистрируем заблокированное действие в step_context
            context.register_step(
                step_number=context.step_context.count() + 1,
                capability_name=action_name or "unknown",
                skill_name="",
                action_item_id=None,
                observation_item_ids=[],
                summary=f"Action blocked by policy: {policy_reason}",
                status=ExecutionStatus.FAILED,
                parameters=parameters,
            )
            
            # Добавляем в agent_state.history для учёта повторов
            context.agent_state.add_step(
                action_name=action_name or "unknown",
                status="blocked",
                parameters=parameters,
                observation={"status": "blocked", "reason": policy_reason},
            )
            
            # Записываем в actions
            context.record_action(
                action_data={
                    "action": decision.action,
                    "parameters": decision.parameters,
                    "status": "blocked",
                    "reason": policy_reason,
                },
                step_number=context.step_context.count(),
            )
            
            # Публикуем событие ошибки
            event_bus = context.application_context.infrastructure_context.event_bus
            import asyncio
            asyncio.create_task(
                event_bus.publish(
                    "ERROR_OCCURRED",
                    {
                        "reason": policy_reason,
                        "action": decision.action,
                        "step": context.step_context.count(),
                    },
                    session_id=context.session_id,
                    agent_id=context.agent_id,
                )
            )
            
            # Пропускаем этот шаг — следующая итерация цикла получит новое решение
            # Очищаем решение чтобы DecisionHandler сделал новый вызов
            context.step_context._current_decision = None
            return None
        
        # Политика разрешила действие — продолжаем конвейер
        return None
