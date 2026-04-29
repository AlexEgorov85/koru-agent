"""
Фаза обновления контекста: регистрация в SessionContext и обновление состояния.

Ответственность:
- Сохранять данные наблюдения/ошибки в data_context
- Регистрировать шаг в контексте сессии
- Обновлять состояние агента сигналом наблюдения
- Обрабатывать пустые SQL-результаты с диагностикой

Эта фаза инкапсулирует всю логику мутации контекста.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.agent.state import ObservationAnalysis
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata
from core.utils.observation_formatter import format_observation, smart_format_observation


class ContextUpdatePhase:
    """Оркестрирует этап обновления контекста в цикле агента."""
    
    def __init__(
        self,
        log: logging.Logger,
        event_bus: Any,
        error_recovery_handler: Optional[Any] = None,
    ):
        self.log = log
        self.event_bus = event_bus
        self.error_recovery_handler = error_recovery_handler
    
    async def save_and_register(
        self,
        result: ExecutionResult,
        observation: Optional[Any] = None,
        decision_action: str = "",
        decision_parameters: Dict[str, Any] = {},
        session_context: Any = None,
        executed_steps: int = 0,
        decision_reasoning: Optional[str] = None,
        error_recovery_handler: Optional[Any] = None,
    ) -> List[str]:
        """
        Save execution result to data_context and register step.
        
        Args:
            result: ExecutionResult from executor
            observation: ObservationAnalysis from ObservationPhase
            decision_action: Action name
            decision_parameters: Action parameters
            session_context: Session context
            executed_steps: Number of executed steps
            decision_reasoning: Reasoning from decision
            error_recovery_handler: Optional error recovery handler
        
        Returns:
            List of observation item IDs
        """
        # Save result data (returns observation_item_ids)
        observation_item_ids = self.save_result_data(
            result=result,
            decision_action=decision_action,
            decision_parameters=decision_parameters,
            session_context=session_context,
            executed_steps=executed_steps,
            observation=observation,
        )
        
        # Handle empty SQL results
        if result.data in (None, {}, [], "") and error_recovery_handler:
            await self.handle_empty_sql_result(
                decision_action=decision_action,
                decision_parameters=decision_parameters,
                session_context=session_context,
                agent_state=session_context.agent_state,
                error_recovery_handler=error_recovery_handler,
            )
        
        # Register step in session context
        self.register_step(
            session_context=session_context,
            executed_steps=executed_steps,
            decision_action=decision_action,
            decision_reasoning=decision_reasoning,
            observation_item_ids=observation_item_ids,
            result_status=result.status,
            decision_parameters=decision_parameters,
            observation=observation,
        )
        
        return observation_item_ids
    
    def save_observation_analysis(
        self,
        session_context: Any,
        observation_data: Dict[str, Any],
        action_name: str,
        step_number: int,
    ) -> None:
        """
        Сохранить результат анализа наблюдения в историю AgentState.
        
        АРХИТЕКТУРА:
        - Шаг 2.1 плана рефакторинга
        - Использует явный ContextItemType.OBSERVATION_ANALYSIS
        - Не дублирует логику форматирования
        
        Args:
            session_context: Session context
            observation_data: Данные наблюдения (status, quality, insight, hint)
            action_name: Название действия
            step_number: Номер шага
        """
        # Создаём типизированный ObservationAnalysis
        analysis = ObservationAnalysis(
            status=observation_data.get('status', 'unknown'),
            quality=observation_data.get('quality', {}),
            insight=observation_data.get('insight', ''),
            hint=observation_data.get('hint', ''),
            rule_based=observation_data.get('_rule_based', False),
            timestamp=datetime.utcnow().isoformat(),
            action_name=action_name,
            step_number=step_number,
        )
        
        # Сохраняем в историю с автосдвигом старых записей
        session_context.agent_state.push_observation(analysis)
    
    def update_agent_state(
        self,
        session_context: Any,
        executed_steps: int,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        result_status: ExecutionStatus,
        observation_signal: Dict[str, Any],
    ) -> None:
        """
        Update agent state with step outcome and observation.
        
        Args:
            session_context: Session context
            executed_steps: Number of executed steps
            decision_action: Action name
            decision_parameters: Action parameters
            result_status: Execution status
            observation_signal: Observation signal dict
        """
        session_context.agent_state.add_step(
            action_name=decision_action or "unknown",
            status=result_status.value,
            parameters=decision_parameters or {},
            observation=observation_signal,
        )
        session_context.agent_state.register_observation(observation_signal)
    
    def save_result_data(
        self,
        result: ExecutionResult,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        executed_steps: int,
        observation: Optional[Any] = None,
    ) -> List[str]:
        """
        Save execution result to data_context.
        
        Args:
            result: ExecutionResult from executor
            decision_action: Action name
            decision_parameters: Action parameters
            session_context: Session context
            executed_steps: Number of executed steps
            
        Returns:
            List of observation item IDs
        """
        observation_item_ids = []
        items_count_before = (
            session_context.data_context.count()
            if hasattr(session_context, "data_context")
            else -1
        )
        
        if result.status == ExecutionStatus.FAILED:
            # Save error observation
            error_details = {
                "error": result.error or "Неизвестная ошибка",
                "status": "FAILED",
                "capability": decision_action,
                "parameters": decision_parameters or {},
            }
            
            # Add stack trace if available
            if hasattr(result, "traceback") and result.traceback:
                error_details["traceback"] = result.traceback[:2000]
            
            observation_item = ContextItem(
                item_id="",
                session_id=session_context.session_id,
                item_type=ContextItemType.ERROR_LOG,
                content=error_details,
                quick_content=f"❌ {result.error or 'Неизвестная ошибка'}"[:200],
                metadata=ContextItemMetadata(
                    source=decision_action,
                    step_number=executed_steps + 1,
                    capability_name=decision_action,
                    additional_data={
                        "is_error": True,
                        "error_type": (
                            type(result.error).__name__
                            if result.error
                            else "Unknown"
                        ),
                    },
                ),
            )
            
            observation_item_id = session_context.data_context.add_item(observation_item)
            observation_item_ids = [observation_item_id]
            
            items_count_after = session_context.data_context.count()
            self.log.info(
                f"📝 Сохранена ошибка: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                extra={"event_type": EventType.STEP_COMPLETED},
            )
            
        elif result.data in (None, {}, [], ""):
            # Пустой результат - сохраняем как наблюдение для отслеживания
            self.log.info(
                f"⚠️ {decision_action} → ПУСТОЙ РЕЗУЛЬТАТ",
                extra={"event_type": EventType.TOOL_RESULT},
            )

            # Записать пустой результат в состояние агента
            self._record_empty_result(
                action_name=decision_action,
                parameters=decision_parameters,
                session_context=session_context,
            )

            # Save empty observation for final_answer visibility
            empty_observation_data = {
                "status": "empty",
                "data": None,
                "action": decision_action,
                "parameters": decision_parameters or {},
            }
            quick_content = f"empty: {decision_action}"
            observation_item = ContextItem(
                item_id="",
                session_id=session_context.session_id,
                item_type=ContextItemType.OBSERVATION,
                content=empty_observation_data,
                quick_content=quick_content,
                metadata=ContextItemMetadata(
                    source=decision_action,
                    step_number=executed_steps + 1,
                    capability_name=decision_action,
                    additional_data={"is_empty": True},
                ),
            )
            observation_item_id = session_context.data_context.add_item(observation_item)
            observation_item_ids = [observation_item_id]

            items_count_after = session_context.data_context.count()
            self.log.debug(
                f"📝 Сохранено empty observation: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                extra={"event_type": EventType.STEP_COMPLETED},
            )
            
        elif result.data is not None:
            # Save successful observation
            additional_metadata = {}
            
            # save_type должен приходиться из observation (заполнен в ObservationPhase)
            # Если observation есть — берем из него, иначе по умолчанию raw_data
            save_type = "raw_data"  # Fallback
            if observation and hasattr(observation, 'save_type') and observation.save_type:
                save_type = observation.save_type
            additional_metadata["save_type"] = save_type
            
            # Check if data_analysis for formatting
            is_data_analysis = decision_action and "data_analysis" in decision_action
            
            if is_data_analysis:
                # Full format for data_analysis
                quick_content = format_observation(
                    result_data=result.data,
                    capability_name=decision_action,
                    parameters=decision_parameters,
                )
            else:
                # Smart format with truncation for others
                quick_content = smart_format_observation(
                    result_data=result.data,
                    capability_name=decision_action,
                    parameters=decision_parameters,
                )
            
            # Сохраняем сырые данные только если решено сохранить raw_data
            content = result.data if save_type == "raw_data" else quick_content
            
            observation_item = ContextItem(
                item_id="",
                session_id=session_context.session_id,
                item_type=ContextItemType.OBSERVATION,
                content=content,
                quick_content=quick_content,
                metadata=ContextItemMetadata(
                    source=decision_action,
                    step_number=executed_steps + 1,
                    capability_name=decision_action,
                    additional_data=(
                        additional_metadata if additional_metadata else None
                    ),
                ),
            )
            
            observation_item_id = session_context.data_context.add_item(observation_item)
            observation_item_ids = [observation_item_id]
            
            items_count_after = session_context.data_context.count()
            self.log.debug(
                f"📝 Сохранено observation: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                extra={"event_type": EventType.STEP_COMPLETED},
            )
            
            # Log observation in prompt format
            if quick_content:
                self.log.info(
                    f"[OBSERVATION] step={executed_steps + 1} | capability={decision_action}\n{quick_content}",
                    extra={"event_type": EventType.STEP_COMPLETED},
                )
        
        return observation_item_ids
    
    def _record_empty_result(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        session_context: Any,
    ) -> None:
        """Записать пустой результат в состояние агента."""
        session_context.agent_state.register_step_outcome(
            action_name=action_name,
            status="empty",
            parameters=parameters,
            observation={"status": "empty", "data": None},
            error_message=None,
        )
    
    async def handle_empty_sql_result(
        self,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        agent_state: Optional[Any] = None,
        error_recovery_handler: Optional[Any] = None,
    ) -> None:
        """
        Handle empty SQL result with diagnostics.
        
        Args:
            decision_action: Action that returned empty result
            decision_parameters: Action parameters
            session_context: Session context
            agent_state: Agent state for registration (optional, uses session_context.agent_state if not provided)
            error_recovery_handler: Optional handler (overrides self.error_recovery_handler)
        """
        # Get agent_state from session_context if not provided
        if agent_state is None:
            agent_state = session_context.agent_state
        
        handler = error_recovery_handler or self.error_recovery_handler
        
        if not handler:
            # Fallback: just register empty result
            agent_state.register_step_outcome(
                action_name=decision_action,
                status="empty",
                parameters=decision_parameters,
                observation={"status": "empty", "data": None},
                error_message=None,
            )
            return
        
        # Use error recovery handler
        try:
            await handler.handle_empty_sql_result(
                decision_action=decision_action,
                decision_parameters=decision_parameters,
                session_context=session_context,
                agent_state=agent_state,
            )
        except Exception as e:
            if self.log:
                self.log.error(f"Error recovery failed: {e}", exc_info=True)
            
            # Fallback registration
            agent_state.register_step_outcome(
                action_name=decision_action,
                status="empty",
                parameters=decision_parameters,
                observation={"status": "empty", "data": None},
                error_message=None,
            )
    
    def register_step(
        self,
        session_context: Any,
        executed_steps: int,
        decision_action: str,
        decision_reasoning: Optional[str],
        observation_item_ids: List[str],
        result_status: ExecutionStatus,
        decision_parameters: Dict[str, Any],
        observation: Optional[Any] = None,
    ) -> None:
        """
        Register step in session context and update agent state.
        
        Args:
            session_context: Session context to update
            executed_steps: Number of executed steps
            decision_action: Action name
            decision_reasoning: Reasoning from decision
            observation_item_ids: IDs of observation items
            result_status: Execution status
            decision_parameters: Action parameters
            observation: ObservationAnalysis from ObservationPhase
        """
        # Build observation signal from passed observation or create minimal
        if observation:
            observation_signal = observation.model_dump()
        else:
            observation_signal = {
                "status": result_status.value if hasattr(result_status, 'value') else str(result_status),
                "quality": {},
                "insight": "",
                "hint": "",
            }
        
        # Register step (data stored in data_context, step contains only references)
        # Используем executed_steps + 1 для синхронизации с observation_phase
        session_context.register_step(
            step_number=executed_steps + 1,
            capability_name=decision_action or "unknown",
            skill_name=(decision_action or "unknown").split(".")[0],
            action_item_id="",
            observation_item_ids=observation_item_ids,
            summary=decision_reasoning,
            status=result_status,
            parameters=decision_parameters or {},
        )
        
        # Update agent state with observation
        session_context.agent_state.add_step(
            action_name=decision_action or "unknown",
            status=result_status.value if hasattr(result_status, 'value') else str(result_status),
            parameters=decision_parameters or {},
            observation=observation_signal,
        )
        
        session_context.agent_state.register_observation(observation_signal)
        
        # Сохраняем в историю наблюдений (окно 3 шт. для промпта LLM)
        if observation:
            session_context.agent_state.push_observation(observation)
