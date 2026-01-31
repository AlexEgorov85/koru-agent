"""
Executor for atomic actions in the agent architecture.
"""

import logging
from typing import Any, Dict, Optional, Union
from core.atomic_actions.base import AtomicAction
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType


logger = logging.getLogger(__name__)


class AtomicActionExecutor:
    """
    Executor for atomic actions that provides complete execution functionality.
    
    This executor handles the full lifecycle of atomic action execution,
    including preparation, execution, result processing, and integration
    with the agent's decision-making system.
    """
    
    def __init__(self, runtime: AgentRuntimeInterface):
        """
        Initialize the atomic action executor.
        
        Args:
            runtime: The agent runtime interface
        """
        self.runtime = runtime
    
    async def execute_atomic_action(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute an atomic action with full lifecycle management.
        
        Args:
            action: The atomic action to execute
            context: The execution context
            parameters: Optional parameters for the action
            
        Returns:
            StrategyDecision representing the outcome of execution
        """
        try:
            # Log the beginning of action execution
            logger.info(f"Executing atomic action: {action.name} - {action.description}")
            
            # Validate inputs
            if not isinstance(action, AtomicAction):
                raise TypeError(f"Expected AtomicAction, got {type(action)}")
            
            # Prepare the context for execution
            prepared_context = await self._prepare_context(context, action, parameters)
            
            # Execute the atomic action
            result = await action.execute(self.runtime, prepared_context, parameters)
            
            # Process the result and integrate with agent state
            processed_result = await self._process_result(result, action, context)
            
            # Log successful completion
            logger.info(f"Completed atomic action: {action.name}, result: {processed_result.action.value}")
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Error executing atomic action {action.name}: {str(e)}", exc_info=True)
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="atomic_action_execution_failed",
                payload={"error": str(e), "action_name": action.name}
            )
    
    async def execute_atomic_action_by_type(
        self,
        action_type: str,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute an atomic action by its type name.
        
        Args:
            action_type: The type of atomic action to execute (e.g., "THINK", "ACT")
            context: The execution context
            parameters: Optional parameters for the action
            
        Returns:
            StrategyDecision representing the outcome of execution
        """
        # Map action type to actual action instance
        action_map = {
            "THINK": lambda: self._create_action_instance("THINK"),
            "ACT": lambda: self._create_action_instance("ACT"),
            "OBSERVE": lambda: self._create_action_instance("OBSERVE"),
            "PLAN": lambda: self._create_action_instance("PLAN"),
            "REFLECT": lambda: self._create_action_instance("REFLECT"),
            "EVALUATE": lambda: self._create_action_instance("EVALUATE"),
            "VERIFY": lambda: self._create_action_instance("VERIFY"),
            "ADAPT": lambda: self._create_action_instance("ADAPT")
        }
        
        if action_type.upper() not in action_map:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="unsupported_atomic_action_type",
                payload={"error": f"Unsupported atomic action type: {action_type}", "available_types": list(action_map.keys())}
            )
        
        action = action_map[action_type.upper()]()
        return await self.execute_atomic_action(action, context, parameters)
    
    async def execute_multiple_atomic_actions(
        self,
        actions: list[AtomicAction],
        context: Any,
        parameters: Optional[Dict[str, Any]] = None,
        sequential: bool = True
    ) -> list[StrategyDecision]:
        """
        Execute multiple atomic actions either sequentially or in parallel.
        
        Args:
            actions: List of atomic actions to execute
            context: The execution context
            parameters: Optional parameters for the actions
            sequential: Whether to execute actions sequentially (True) or in parallel (False)
            
        Returns:
            List of StrategyDecisions representing the outcomes of execution
        """
        results = []
        if sequential:
            for action in actions:
                result = await self.execute_atomic_action(action, context, parameters)
                results.append(result)
                # Check if we should stop based on the result
                if result.action.is_terminal():
                    break
        else:
            # For parallel execution, we would need to implement async execution
            # For now, we'll just execute sequentially as a fallback
            for action in actions:
                result = await self.execute_atomic_action(action, context, parameters)
                results.append(result)
                # Check if we should stop based on the result
                if result.action.is_terminal():
                    break
        
        return results
    
    async def _prepare_context(self, context: Any, action: AtomicAction, parameters: Optional[Dict[str, Any]]) -> Any:
        """
        Prepare the execution context for an atomic action.
        
        Args:
            context: The original execution context
            action: The atomic action to prepare context for
            parameters: Parameters for the action
            
        Returns:
            Prepared context for the action
        """
        # For now, return the context as is, but in the future this could
        # include action-specific context preparation
        return context
    
    async def _process_result(self, result: StrategyDecision, action: AtomicAction, context: Any) -> StrategyDecision:
        """
        Process the result of an atomic action execution.
        
        Args:
            result: The result from the atomic action execution
            action: The atomic action that was executed
            context: The execution context
            
        Returns:
            Processed strategy decision
        """
        # Add action-specific information to the result
        if result.payload is None:
            result.payload = {}
        
        # Add information about which action was executed
        result.payload.update({
            "executed_action": action.name,
            "action_type": action.__class__.__name__
        })
        
        return result
    
    def _create_action_instance(self, action_type: str) -> AtomicAction:
        """
        Create an instance of an atomic action by type name.
        
        Args:
            action_type: The type of atomic action to create (e.g., "THINK", "ACT")
            
        Returns:
            Instance of the atomic action
        """
        from core.atomic_actions.actions import (
            THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT
        )
        
        action_classes = {
            "THINK": THINK,
            "ACT": ACT,
            "OBSERVE": OBSERVE,
            "PLAN": PLAN,
            "REFLECT": REFLECT,
            "EVALUATE": EVALUATE,
            "VERIFY": VERIFY,
            "ADAPT": ADAPT
        }
        
        if action_type not in action_classes:
            raise ValueError(f"Unknown atomic action type: {action_type}")
        
        return action_classes[action_type]()