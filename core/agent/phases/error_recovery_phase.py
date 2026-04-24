"""
Error Recovery Step: SQL diagnostics and empty result handling.

Responsibility:
- Diagnose empty SQL results
- Provide actionable suggestions for SyntaxError and TimeoutError
- Handle policy violations with recovery strategies
- Return DiagnosticSignal for Pattern

This step encapsulates all error recovery logic.
"""

import logging
from typing import Any, Dict, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionStatus


class ErrorRecoveryPhase:
    """Orchestrates the error recovery stage of the agent loop."""
    
    def __init__(
        self,
        sql_diagnostic_service: Optional[Any] = None,
        log: Optional[logging.Logger] = None,
    ):
        self.sql_diagnostic_service = sql_diagnostic_service
        self.log = log
    
    async def handle_empty_sql_result(
        self,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        agent_state: Any,
    ) -> None:
        """
        Handle empty SQL result with diagnostics.
        
        Args:
            decision_action: Action that returned empty result
            decision_parameters: Action parameters
            session_context: Session context
            agent_state: Agent state for registration
        """
        if not self.sql_diagnostic_service:
            # Fallback: just register empty result
            agent_state.register_step_outcome(
                action_name=decision_action,
                status="empty",
                parameters=decision_parameters,
                observation={"status": "empty", "data": None},
                error_message=None,
            )
            return
        
        # Use SQL diagnostic service
        try:
            diagnostic = await self.sql_diagnostic_service.diagnose_empty_result(
                capability_name=decision_action,
                parameters=decision_parameters,
                session_context=session_context,
            )
            
            # Log diagnostic result
            if self.log:
                self.log.info(
                    f"🔍 SQL Diagnostic: {diagnostic.get('diagnosis', 'N/A')}",
                    extra={"event_type": EventType.INFO},
                )
            
            # Register outcome with diagnostic info
            agent_state.register_step_outcome(
                action_name=decision_action,
                status="empty",
                parameters=decision_parameters,
                observation={
                    "status": "empty",
                    "data": None,
                    "diagnostic": diagnostic,
                },
                error_message=None,
            )
            
        except Exception as e:
            if self.log:
                self.log.error(f"SQL diagnostic failed: {e}", exc_info=True)
            
            # Fallback registration
            agent_state.register_step_outcome(
                action_name=decision_action,
                status="empty",
                parameters=decision_parameters,
                observation={"status": "empty", "data": None},
                error_message=None,
            )
    
    async def handle_failed_execution(
        self,
        decision_action: str,
        result_error: str,
        result_status: ExecutionStatus,
        session_context: Any,
        agent_state: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle failed execution with diagnostics.
        
        Args:
            decision_action: Action that failed
            result_error: Error message from result
            result_status: Execution status (FAILED)
            session_context: Session context
            agent_state: Agent state
            
        Returns:
            Diagnostic signal dict or None
        """
        if not self.sql_diagnostic_service or not result_error:
            return None
        
        # Parse error type
        error_type = self._classify_error(result_error)
        
        try:
            if error_type == "syntax_error":
                # SyntaxError: suggest EXPLAIN or simplify SELECT
                diagnostic = {
                    "error_type": "syntax_error",
                    "suggestion": "Попробуйте упростить запрос или использовать EXPLAIN для отладки",
                    "actionable": True,
                }
                
            elif error_type == "timeout":
                # TimeoutError: suggest LIMIT or index
                diagnostic = {
                    "error_type": "timeout",
                    "suggestion": "Добавьте LIMIT или проверьте наличие индексов",
                    "actionable": True,
                }
                
            elif error_type == "semantic_empty":
                # Semantic empty: use SQL diagnostic service
                diagnostic = await self.sql_diagnostic_service.diagnose_semantic_empty(
                    capability_name=decision_action,
                    error_message=result_error,
                    session_context=session_context,
                )
                
            else:
                # Unknown error
                diagnostic = {
                    "error_type": "unknown",
                    "suggestion": "Проверьте логи и параметры запроса",
                    "actionable": False,
                }
            
            # Log diagnostic
            if self.log:
                self.log.info(
                    f"🔍 Error Diagnostic [{error_type}]: {diagnostic.get('suggestion', 'N/A')}",
                    extra={"event_type": EventType.INFO},
                )
            
            return diagnostic
            
        except Exception as e:
            if self.log:
                self.log.error(f"Error diagnostic failed: {e}", exc_info=True)
            
            return None
    
    def _classify_error(self, error_message: str) -> str:
        """
        Classify error type from error message.
        
        Args:
            error_message: Error message string
            
        Returns:
            Error type: "syntax_error", "timeout", "semantic_empty", or "unknown"
        """
        error_lower = error_message.lower()
        
        # Syntax errors
        syntax_keywords = [
            "syntax error",
            "parse error",
            "invalid syntax",
            "unexpected token",
            "sql syntax",
        ]
        if any(kw in error_lower for kw in syntax_keywords):
            return "syntax_error"
        
        # Timeout errors
        timeout_keywords = [
            "timeout",
            "timed out",
            "execution time exceeded",
            "query timeout",
        ]
        if any(kw in error_lower for kw in timeout_keywords):
            return "timeout"
        
        # Semantic empty (no results but valid query)
        empty_keywords = [
            "no results",
            "empty result",
            "no rows",
            "zero matches",
        ]
        if any(kw in error_lower for kw in empty_keywords):
            return "semantic_empty"
        
        return "unknown"
