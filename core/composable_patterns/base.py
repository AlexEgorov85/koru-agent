"""
Base classes for composable patterns in the agent architecture.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from core.atomic_actions.base import AtomicAction
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.composable_patterns.state_manager import ComposablePatternStateManager


class ComposablePattern(ABC):
    """
    Abstract base class for composable thinking patterns.
    
    Composable patterns are built from atomic actions and can be dynamically
    assembled to create complex behaviors.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.actions: List[AtomicAction] = []
        self.state_manager = ComposablePatternStateManager()
        self.state_id = None
    
    def add_action(self, action: AtomicAction):
        """Add an atomic action to the pattern."""
        self.actions.append(action)
    
    def remove_action(self, action: AtomicAction):
        """Remove an atomic action from the pattern."""
        if action in self.actions:
            self.actions.remove(action)
    
    def clear_actions(self):
        """Clear all actions from the pattern."""
        self.actions.clear()
    
    @abstractmethod
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the composable pattern.
        
        Args:
            runtime: The agent runtime interface
            context: The execution context
            parameters: Optional parameters for the pattern
            
        Returns:
            StrategyDecision representing the outcome
        """
        pass


class ConcreteComposablePattern(ComposablePattern):
    """
    Concrete implementation of ComposablePattern that executes a sequence of atomic actions.
    """
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Execute the composable pattern by running each atomic action in sequence.
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
            logger.info(f"Executing action {action.name} in pattern {self.name}")
            
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
                logger.info(f"Terminating pattern execution early due to terminal action: {result.action.value}")
                self.state_manager.complete(self.state_id)
                return result
        
        # Return the result of the last action or a successful completion decision
        if self.actions:
            logger.info(f"Pattern {self.name} completed successfully with {len(self.actions)} actions executed")
            self.state_manager.complete(self.state_id)
            return result  # Return the last action's result
        else:
            logger.info(f"Pattern {self.name} completed with no actions")
            self.state_manager.complete(self.state_id)
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                reason="pattern_executed_no_actions",
                payload={"pattern_name": self.name, "actions_count": 0}
            )


class PatternBuilder:
    """
    Builder class for creating composable patterns dynamically.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        # Создаем экземпляр ConcreteComposablePattern вместо абстрактного класса
        self.pattern = ConcreteComposablePattern(name, description)
    
    def add_think(self) -> 'PatternBuilder':
        """Add a THINK action to the pattern."""
        from core.atomic_actions.actions import THINK
        self.pattern.add_action(THINK())
        return self
    
    def add_act(self) -> 'PatternBuilder':
        """Add an ACT action to the pattern."""
        from core.atomic_actions.actions import ACT
        self.pattern.add_action(ACT())
        return self
    
    def add_observe(self) -> 'PatternBuilder':
        """Add an OBSERVE action to the pattern."""
        from core.atomic_actions.actions import OBSERVE
        self.pattern.add_action(OBSERVE())
        return self
    
    def add_plan(self) -> 'PatternBuilder':
        """Add a PLAN action to the pattern."""
        from core.atomic_actions.actions import PLAN
        self.pattern.add_action(PLAN())
        return self
    
    def add_reflect(self) -> 'PatternBuilder':
        """Add a REFLECT action to the pattern."""
        from core.atomic_actions.actions import REFLECT
        self.pattern.add_action(REFLECT())
        return self
    
    def add_evaluate(self) -> 'PatternBuilder':
        """Add an EVALUATE action to the pattern."""
        from core.atomic_actions.actions import EVALUATE
        self.pattern.add_action(EVALUATE())
        return self
    
    def add_verify(self) -> 'PatternBuilder':
        """Add a VERIFY action to the pattern."""
        from core.atomic_actions.actions import VERIFY
        self.pattern.add_action(VERIFY())
        return self
    
    def add_adapt(self) -> 'PatternBuilder':
        """Add an ADAPT action to the pattern."""
        from core.atomic_actions.actions import ADAPT
        self.pattern.add_action(ADAPT())
        return self
    
    def add_custom_action(self, action: AtomicAction) -> 'PatternBuilder':
        """Add a custom atomic action to the pattern."""
        self.pattern.add_action(action)
        return self
    
    def build(self) -> ComposablePattern:
        """Build and return the composable pattern."""
        return self.pattern
