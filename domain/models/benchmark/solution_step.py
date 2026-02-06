"""
Модель шага алгоритма решения
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class StepType(str, Enum):
    """
    Тип шага в алгоритме решения
    """
    ANALYSIS = "analysis"
    DISCOVERY = "discovery"
    EXECUTION = "execution"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"


@dataclass
class SolutionStep:
    """
    Шаг алгоритма решения
    """
    step_number: int
    description: str
    expected_action: str
    expected_observation: str
    required_capability: str
    estimated_complexity: int = 1
    step_type: StepType = StepType.EXECUTION
    required_skills: Optional[list] = None
    expected_tools: Optional[list] = None
    
    def __post_init__(self):
        """Инициализация значений по умолчанию."""
        if self.required_skills is None:
            self.required_skills = []
        if self.expected_tools is None:
            self.expected_tools = []