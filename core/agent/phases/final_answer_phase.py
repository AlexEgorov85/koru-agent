"""
Final Answer Step: Final answer generation (FINISH decision or fallback).

Responsibility:
- Generate final answer when Pattern decides FINISH
- Generate fallback answer when step limit is reached
- Handle Pydantic response validation
- Commit dialogue and sync history

This step encapsulates all finalization logic.
"""

import logging
from typing import Any, Callable, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult


class FinalAnswerPhase:
    """Orchestrates the final answer stage of the agent loop."""
    
    def __init__(
        self,
        safe_executor: Any,
        agent_config: Optional[Any],
        log: logging.Logger,
        event_bus: Any,
    ):
        self.safe_executor = safe_executor
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
            # Get final_answer component from pattern or create
            from core.components.component_factory import ComponentFactory
            from core.config.component_config import ComponentConfig
            
            behavior_configs = getattr(session_context, '_behavior_configs', {})
            component_config = behavior_configs.get("final_answer")
            
            if not component_config:
                component_config = ComponentConfig(
                    name="final_answer", variant_id="default"
                )
            
            factory = ComponentFactory(
                infrastructure_context=session_context._infrastructure_context
                if hasattr(session_context, '_infrastructure_context')
                else None
            )
            
            # Try to get final_answer from application_context
            app_ctx = getattr(session_context, '_application_context', None)
            if app_ctx:
                from core.agent.behaviors.evaluation.final_answer import FinalAnswerGenerator
                
                final_answer = await factory.create_and_initialize(
                    component_class=FinalAnswerGenerator,
                    name="final_answer",
                    application_context=app_ctx,
                    component_config=component_config,
                )
                
                # Generate final answer
                result = await final_answer.generate(
                    session_context=session_context,
                    goal=goal,
                )
                
                if result:
                    # Commit dialogue
                    session_context.commit_turn(
                        user_query=goal,
                        assistant_response=result.get("answer", "") if isinstance(result, dict) else str(result),
                        tools_used=[],
                    )
                    sync_dialogue_callback()
                    
                    return ExecutionResult.success(
                        data=result if isinstance(result, dict) else {"answer": str(result)}
                    )
                    
        except Exception as e:
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
        
        Args:
            session_context: Session context with collected data
            session_id: Current session ID
            agent_id: Current agent ID
            goal: Original goal
            executed_steps: Number of steps executed
            sync_dialogue_callback: Callback to sync dialogue history
            
        Returns:
            ExecutionResult with fallback message
        """
        self.log.warning(
            f"Лимит шагов ({session_context._max_steps if hasattr(session_context, '_max_steps') else 'N/A'}) исчерпан. "
            f"Пытаюсь сгенерировать итоговый ответ на основе {executed_steps} шагов..."
        )
        
        try:
            # Try to synthesize answer from collected data
            from core.components.component_factory import ComponentFactory
            from core.config.component_config import ComponentConfig
            
            behavior_configs = getattr(session_context, '_behavior_configs', {})
            component_config = behavior_configs.get("final_answer")
            
            if not component_config:
                component_config = ComponentConfig(
                    name="final_answer", variant_id="default"
                )
            
            # Get infrastructure context
            infra_ctx = None
            if hasattr(session_context, '_infrastructure_context'):
                infra_ctx = session_context._infrastructure_context
            
            factory = ComponentFactory(infrastructure_context=infra_ctx)
            
            app_ctx = getattr(session_context, '_application_context', None)
            if app_ctx:
                from core.agent.behaviors.evaluation.final_answer import FinalAnswerGenerator
                
                final_answer = await factory.create_and_initialize(
                    component_class=FinalAnswerGenerator,
                    name="final_answer",
                    application_context=app_ctx,
                    component_config=component_config,
                )
                
                # Generate fallback answer
                result = await final_answer.generate(
                    session_context=session_context,
                    goal=goal,
                )
                
                if result:
                    session_context.commit_turn(
                        user_query=goal,
                        assistant_response=result.get("answer", "") if isinstance(result, dict) else str(result),
                        tools_used=[],
                    )
                    sync_dialogue_callback()
                    
                    return ExecutionResult.success(
                        data=result if isinstance(result, dict) else {"answer": str(result)}
                    )
                    
        except Exception as e:
            self.log.error(f"Не удалось сгенерировать fallback-ответ: {e}")
        
        # Ultimate fallback
        fallback_msg = f"Не удалось достичь цели за {executed_steps} шагов."
        if executed_steps == 0:
            fallback_msg += " Действия не выполнялись."
        else:
            fallback_msg += f" Собрано данных за {executed_steps} шагов, но синтез ответа не удался."
        
        session_context.commit_turn(
            user_query=goal,
            assistant_response=fallback_msg,
            tools_used=[],
        )
        sync_dialogue_callback()
        
        return ExecutionResult.failure(fallback_msg)
