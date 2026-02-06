"""
Модель алгоритма решения
"""
from dataclasses import dataclass
from typing import List
from domain.models.benchmark.solution_step import SolutionStep


@dataclass
class SolutionAlgorithm:
    """
    Модель алгоритма решения задачи
    """
    steps: List[SolutionStep]
    required_skills: List[str]
    expected_tools: List[str]
    validation_criteria: List[str]
    description: str = ""
    
    def get_step_by_number(self, step_number: int) -> SolutionStep:
        """Получить шаг по номеру"""
        for step in self.steps:
            if step.step_number == step_number:
                return step
        raise ValueError(f"Step with number {step_number} not found")
    
    def get_total_complexity(self) -> int:
        """Получить общую сложность алгоритма"""
        return sum(step.estimated_complexity for step in self.steps)