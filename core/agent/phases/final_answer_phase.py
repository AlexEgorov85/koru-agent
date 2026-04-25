"""
Фаза финального ответа: генерация финального ответа (решение FINISH или fallback).

Ответственность:
- Генерировать финальный ответ при решении FINISH
- Генерировать fallback-ответ при достижении лимита шагов
- Обрабатывать валидацию ответа через Pydantic
- Фиксировать диалог и синхронизировать историю

Эта фаза инкапсулирует всю логику финализации.
"""

import logging
from typing import Any, Callable, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus


class FinalAnswerPhase:
    """Orchestrates the final answer stage of the agent loop."""
    
    def __init__(
        self,
        application_context: Any,
        executor: Any,
        agent_config: Optional[Any],
        log: logging.Logger,
        event_bus: Any,
    ):
        self.application_context = application_context
        self.executor = executor
        self.agent_config = agent_config
        self.log = log
        self.event_bus = event_bus
    
    async def generate_final_answer(
        self,
        session_context: Any,
        session_id: str,
        agent_id: str,
        goal: str,
        decision_reasoning: Optional[str],
        sync_dialogue_callback: Callable[[], None],
    ) -> Optional[ExecutionResult]:
        """
        Generate final answer when Pattern decides FINISH.
        
        Args:
            session_context: Session context with collected data
            session_id: Current session ID
            agent_id: Current agent ID
            goal: Original goal
            decision_reasoning: Reasoning from FINISH decision
            sync_dialogue_callback: Callback to sync dialogue history
            
        Returns:
            ExecutionResult with final answer or None to use default
        """
        self.log.info(
            f"Завершение: {decision_reasoning if decision_reasoning else 'готов'}. "
            f"Запускаю final_answer.generate...",
            extra={"event_type": EventType.AGENT_STOP},
        )
        
        try:
            # Вызов final_answer.generate через executor
            from core.components.action_executor import ExecutionContext
            
            execution_context = ExecutionContext(
                session_context=session_context,
                session_id=session_id,
                agent_id=agent_id,
            )
            
            result = await self.executor.execute_action(
                action_name="final_answer.generate",
                parameters={
                    "goal": goal,
                    "format_type": "structured",
                    "include_steps": True,
                    "include_evidence": True,
                    "decision_reasoning": decision_reasoning,
                },
                context=execution_context,
            )
            
            if result and result.status == ExecutionStatus.COMPLETED:
                data = result.data if hasattr(result, 'data') else result
                final_answer_text = ""
                if isinstance(data, dict):
                    # Приоритет: final_answer (по контракту), затем answer (legacy), затем другие поля
                    final_answer_text = data.get("final_answer") or data.get("answer", "")
                else:
                    final_answer_text = str(data)
                
                session_context.commit_turn(
                    user_query=goal,
                    assistant_response=final_answer_text,
                    tools_used=["final_answer.generate"],
                )
                sync_dialogue_callback()
                
                return ExecutionResult.success(data=data)
                    
        except Exception as e:
            if self.log:
                self.log.error(f"Ошибка генерации финального ответа: {e}", exc_info=True)
        
        return None
    
    async def generate_fallback_answer(
        self,
        session_context: Any,
        session_id: str,
        agent_id: str,
        goal: str,
        executed_steps: int,
        sync_dialogue_callback: Callable[[], None],
    ) -> ExecutionResult:
        """
        Generate fallback answer when step limit is reached.
        
        ARGS:
            session_context: Session context with collected data
            session_id: Current session ID
            agent_id: Current agent ID
            goal: Original goal
            executed_steps: Number of steps executed
            sync_dialogue_callback: Callback to sync dialogue history
            
        RETURNS:
            ExecutionResult with fallback message
        """
        self.log.warning(
            f"Лимит шагов ({session_context._max_steps if hasattr(session_context, '_max_steps') else 'N/A'}) исчерпан. "
            f"Пытаюсь сгенерировать итоговый ответ на основе {executed_steps} шагов..."
        )
        
        try:
            # Вызов final_answer.generate через executor (как в generate_final_answer)
            from core.components.action_executor import ExecutionContext
            
            execution_context = ExecutionContext(
                session_context=session_context,
                session_id=session_id,
                agent_id=agent_id,
            )
            
            result = await self.executor.execute_action(
                action_name="final_answer.generate",
                parameters={
                    "goal": goal,
                    "format_type": "structured",
                    "include_steps": True,
                    "include_evidence": True,
                    "is_fallback": True,
                    "executed_steps": executed_steps,
                },
                context=execution_context,
            )
            
            if result and result.status == ExecutionStatus.COMPLETED:
                data = result.data if hasattr(result, 'data') else result
                fallback_text = ""
                if isinstance(data, dict):
                    # Приоритет: final_answer (по контракту), затем answer (legacy)
                    fallback_text = data.get("final_answer") or data.get("answer", "")
                else:
                    fallback_text = str(data)
                    
                session_context.commit_turn(
                    user_query=goal,
                    assistant_response=fallback_text,
                    tools_used=["final_answer.generate"],
                )
                sync_dialogue_callback()
                
                return ExecutionResult.success(data=data)
                
        except Exception as e:
            self.log.error(f"Не удалось сгенерировать fallback-ответ: {e}", exc_info=True)
        
        # Ultimate fallback
        fallback_msg = f"Не удалось достичь цели за {executed_steps} шагов."
        if executed_steps == 0:
            fallback_msg += " Действия не выполнялись."
        else:
            fallback_msg += f" Собрано данных за {executed_steps} шагов, но синтез ответа не удался."
        
        session_context.commit_turn(
            user_query=goal,
            assistant_response=fallback_msg,
            tools_used=[]
        )
        sync_dialogue_callback()
        
        return ExecutionResult.failure(fallback_msg)
