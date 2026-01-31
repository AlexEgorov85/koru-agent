"""
Predefined composable patterns for common agent behaviors.
"""

import time
from typing import Any, Dict, List, Optional
from core.composable_patterns.base import ComposablePattern
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.atomic_actions.actions import THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT


class ReActPattern(ComposablePattern):
    """
    ReAct (Reasoning + Acting) pattern implementation.
    Alternates between reasoning (think) and acting (act) steps.
    """
    
    def __init__(self, name: str = "react_composable", description: str = "Composable ReAct pattern"):
        super().__init__(name, description)
        # Initialize with basic ReAct sequence: Think -> Act -> Observe -> Think -> Act...
        self.add_action(THINK())
        self.add_action(ACT())
        self.add_action(OBSERVE())
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the ReAct pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in ReAct pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating ReAct pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"ReAct pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"ReAct pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="react_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class PlanAndExecutePattern(ComposablePattern):
    """
    Plan and Execute pattern implementation.
    Creates a plan first, then executes it step by step.
    """
    
    def __init__(self, name: str = "plan_and_execute_composable", description: str = "Composable Plan and Execute pattern"):
        super().__init__(name, description)
        # Initialize with Plan -> Execute sequence
        self.add_action(PLAN())
        self.add_action(THINK())  # For reasoning during execution
        self.add_action(ACT())    # For taking actions
        self.add_action(OBSERVE()) # For observing results
        self.add_action(EVALUATE()) # For evaluating progress
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Plan and Execute pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in PlanAndExecute pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating PlanAndExecute pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"PlanAndExecute pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"PlanAndExecute pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="plan_and_execute_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class ToolUsePattern(ComposablePattern):
    """
    Tool Use pattern implementation.
    Focuses on selecting and using appropriate tools to achieve goals.
    """
    
    def __init__(self, name: str = "tool_use_composable", description: str = "Composable Tool Use pattern"):
        super().__init__(name, description)
        # Initialize with Think -> Select Tool -> Act -> Observe cycle
        self.add_action(THINK())
        self.add_action(ACT())  # This would include tool selection
        self.add_action(OBSERVE())
        self.add_action(VERIFY())  # Verify tool usage result
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Tool Use pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in ToolUse pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating ToolUse pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"ToolUse pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"ToolUse pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="tool_use_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class ReflectionPattern(ComposablePattern):
    """
    Reflection pattern implementation.
    Includes periodic reflection on past actions and learning.
    """
    
    def __init__(self, name: str = "reflection_composable", description: str = "Composable Reflection pattern"):
        super().__init__(name, description)
        # Initialize with Think -> Act -> Reflect cycle
        self.add_action(THINK())
        self.add_action(ACT())
        self.add_action(REFLECT())  # Reflect on action taken
        self.add_action(ADAPT())    # Adapt based on reflection
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Reflection pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in Reflection pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating Reflection pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"Reflection pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"Reflection pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="reflection_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


# Domain-specific patterns
class CodeAnalysisPattern(ComposablePattern):
    """
    Domain-specific pattern for code analysis tasks.
    """
    
    def __init__(self, name: str = "code_analysis", description: str = "Pattern for code analysis tasks"):
        super().__init__(name, description)
        self.add_action(THINK())      # Understand code structure
        self.add_action(OBSERVE())    # Examine code
        self.add_action(ACT())        # Use code analysis tools
        self.add_action(THINK())      # Analyze findings
        self.add_action(VERIFY())     # Verify analysis results
        self.add_action(REFLECT())    # Reflect on code quality
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Code Analysis pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in CodeAnalysis pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating CodeAnalysis pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"CodeAnalysis pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"CodeAnalysis pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="code_analysis_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class DatabaseQueryPattern(ComposablePattern):
    """
    Domain-specific pattern for database query tasks.
    """
    
    def __init__(self, name: str = "database_query", description: str = "Pattern for database query tasks"):
        super().__init__(name, description)
        self.add_action(THINK())      # Understand query requirements
        self.add_action(ACT())        # Execute query
        self.add_action(OBSERVE())    # Observe results
        self.add_action(VERIFY())     # Verify results
        self.add_action(EVALUATE())   # Evaluate if results meet requirements
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Database Query pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in DatabaseQuery pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating DatabaseQuery pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"DatabaseQuery pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"DatabaseQuery pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="database_query_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class ResearchPattern(ComposablePattern):
    """
    Domain-specific pattern for research tasks.
    """
    
    def __init__(self, name: str = "research", description: str = "Pattern for research tasks"):
        super().__init__(name, description)
        self.add_action(THINK())      # Define research question
        self.add_action(ACT())        # Search for information
        self.add_action(OBSERVE())    # Gather information
        self.add_action(EVALUATE())   # Evaluate sources
        self.add_action(REFLECT())    # Synthesize findings
        self.add_action(VERIFY())     # Verify facts
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the Research pattern by running each atomic action in sequence.
        """
        from core.atomic_actions.executor import AtomicActionExecutor
        import logging

        logger = logging.getLogger(__name__)

        # Initialize state for this execution if not already initialized
        if self.state_id is None:
            self.state_id = f"{self.name}_{id(self)}_{int(time.time())}"
            self.state_manager.create_state(self.name, self.description, self.state_id)
            self.state_manager.update_state(self.state_id, {"status": "active"})

        # Update step count
        current_state = self.state_manager.get_state(self.state_id)
        if current_state:
            current_state.step += 1
            self.state_manager.update_state(self.state_id, {"step": current_state.step})

        # Initialize atomic action executor
        executor = AtomicActionExecutor(runtime)
        
        # Execute each action in sequence with full lifecycle management
        for i, action in enumerate(self.actions):
            # Update state to reflect action execution
            self.state_manager.start_action_execution(self.state_id, action.name)
            logger.info(f"Executing action {action.name} in Research pattern")
            result = await executor.execute_atomic_action(action, context, parameters)
            
            # Log the result of the action
            logger.info(f"Action {action.name} completed with result: {result.action.value}")
            
            # Update state with action result
            self.state_manager.finish_action_execution(self.state_id, {
                "action_name": action.name,
                "result": result,
                "timestamp": time.time()
            })
            
            # Check if the result indicates we should terminate early
            if result.action.is_terminal() if hasattr(result.action, 'is_terminal') else result.action in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]:
                logger.info(f"Terminating Research pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"Research pattern completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"Research pattern completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="research_pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )
