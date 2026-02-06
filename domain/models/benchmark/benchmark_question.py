"""
Модель вопроса бенчмарка
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from domain.models.benchmark.solution_algorithm import SolutionAlgorithm


@dataclass
class BenchmarkQuestion:
    """
    Модель вопроса бенчмарка с эталонным решением
    """
    question_id: str
    question_text: str
    expected_answer: str
    solution_algorithm: SolutionAlgorithm
    category: str
    difficulty_level: int
    metadata: Optional[Dict] = None
    created_at: datetime = None
    
    def __post_init__(self):
        """Инициализация значений по умолчанию."""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}