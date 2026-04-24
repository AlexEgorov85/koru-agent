"""
Execution Step: SafeExecutor.execute() with result handling.

Responsibility:
- Execute action through SafeExecutor (with or without step config)
- Handle execution exceptions
- Log results and publish events
- Return ExecutionResult

This step encapsulates all execution logic including error handling.
"""

import logging
from typing import Any, Dict, Optional

from core.components.action_executor import ExecutionContext
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus


class ExecutionPhase:
    """Orchestrates the execution stage of the agent loop."""
    
    def __init__(
        self,
        safe_executor: Any,
        log: logging.Logger,
        event_bus: Any,
        agent_config: Optional[Any] = None,
    ):
        self.safe_executor = safe_executor
        self.log = log
        self.event_bus = event_bus
        self.agent_config = agent_config
    
    async def execute(
        self,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        session_id: str,
        agent_id: str,
        step_number: int,
    ) -> ExecutionResult:
        """
        Execute action through SafeExecutor.
        
        Args:
            decision_action: Action name from decision
            decision_parameters: Action parameters from decision
            session_context: Session context for execution
            session_id: Current session ID
            agent_id: Current agent ID
            step_number: Step number for logging
            
        Returns:
            ExecutionResult from safe_executor
        """
        self.log.info(
            f"⚙️ Запускаю {decision_action} с параметрами: {decision_parameters or {}}",
            extra={"event_type": EventType.TOOL_CALL},
        )
        
        self.log.info(
            f"⚙️ Executor.execute({decision_action})...",
            extra={"event_type": EventType.TOOL_CALL},
        )
        
        # Find step config if available
        step_config = None
        if self.agent_config and hasattr(self.agent_config, 'steps'):
            for sid, cfg in self.agent_config.steps.items():
                if cfg.capability == decision_action:
                    step_config = cfg
                    break
        
        try:
            # Execute with or without config
            if step_config:
                result = await self.safe_executor.execute_with_config(
                    step_config=step_config,
                    parameters=decision_parameters or {},
                    context=ExecutionContext(
                        session_context=session_context,
                        session_id=session_id,
                        agent_id=agent_id,
                    ),
                    step_id=f"step_{sid}_{step_number}",
                )
            else:
                result = await self.safe_executor.execute(
                    capability_name=decision_action,
                    parameters=decision_parameters or {},
                    context=ExecutionContext(
                        session_context=session_context,
                        session_id=session_id,
                        agent_id=agent_id,
                    ),
                )
            
            # Log result
            if result.status == ExecutionStatus.FAILED:
                self.log.error(
                    f"❌ Действие {decision_action} завершилось с ошибкой: {result.error or 'неизвестная'}",
                    extra={"event_type": EventType.TOOL_ERROR},
                )
            else:
                self.log.info(
                    f"✅ Действие {decision_action} выполнено",
                    extra={"event_type": EventType.TOOL_RESULT},
                )
                
        except Exception as e:
            # SafeExecutor shouldn't throw but handle just in case
            self.log.error(
                f"❌ Исключение при выполнении {decision_action}: {e}",
                extra={"event_type": EventType.TOOL_ERROR},
                exc_info=True,
            )
            result = ExecutionResult.failure(str(e))
        
        # Publish execution event
        await self.event_bus.publish(
            EventType.ACTION_PERFORMED,
            {
                "action": decision_action,
                "parameters": decision_parameters or {},
                "status": result.status.value,
                "error": result.error,
                "step": step_number,
            },
            session_id=session_id,
            agent_id=agent_id,
        )
        
        # Log for UI
        if result.status == ExecutionStatus.FAILED:
            self.log.info(
                f"❌ {decision_action} → FAILED: {result.error or 'неизвестная'}",
                extra={"event_type": EventType.TOOL_ERROR},
            )
        else:
            self.log.info(
                f"✅ {decision_action} → {result.status.value}",
                extra={"event_type": EventType.TOOL_RESULT},
            )
        
        return result
