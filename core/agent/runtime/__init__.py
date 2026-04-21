"""
Runtime package for agent execution.

Provides:
- AgentRuntime: Main runtime orchestrator
- ExecutionPipeline: Step execution pipeline
- Handlers: Decision, Policy, Action handlers
- Strategies: Termination strategies
- Recorders: Observation recorders
"""

from core.agent.runtime.runtime import AgentRuntime
from core.agent.runtime.pipeline import ExecutionPipeline
from core.agent.runtime.handlers.base import IStepHandler
from core.agent.runtime.handlers.decision import DecisionHandler
from core.agent.runtime.handlers.policy import PolicyCheckHandler
from core.agent.runtime.handlers.action import ActionHandler
from core.agent.runtime.strategies.termination import (
    ITerminationStrategy,
    DefaultTerminationStrategy,
)
from core.agent.runtime.recorders.observation import (
    IObservationRecorder,
    DefaultObservationRecorder,
)

__all__ = [
    "AgentRuntime",
    "ExecutionPipeline",
    "IStepHandler",
    "DecisionHandler",
    "PolicyCheckHandler",
    "ActionHandler",
    "ITerminationStrategy",
    "DefaultTerminationStrategy",
    "IObservationRecorder",
    "DefaultObservationRecorder",
]
