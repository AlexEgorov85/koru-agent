"""
Инициализация компонента субагентов.
"""
from .base_sub_agent import BaseSubAgent
from .sub_agent_factory import SubAgentFactory
from .code_analysis_sub_agent import CodeAnalysisSubAgent
from .research_sub_agent import ResearchSubAgent
from .planning_sub_agent import PlanningSubAgent
from .execution_sub_agent import ExecutionSubAgent

__all__ = [
    'BaseSubAgent',
    'SubAgentFactory',
    'CodeAnalysisSubAgent',
    'ResearchSubAgent',
    'PlanningSubAgent',
    'ExecutionSubAgent'
]
