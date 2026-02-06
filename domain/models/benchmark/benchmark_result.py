"""
Модель результата бенчмарка
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class BenchmarkResult:
    """
    Модель результата бенчмарка
    """
    benchmark_id: str
    question_id: str
    agent_response: str
    expected_answer: str
    similarity_score: float
    evaluation_metrics: Dict
    timestamp: datetime = None
    deviation_points: Optional[List[Dict]] = None
    solution_path_accuracy: Optional[float] = None
    step_by_step_evaluation: Optional[List[Dict]] = None
    
    def __post_init__(self):
        """Инициализация значений по умолчанию."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.deviation_points is None:
            self.deviation_points = []
        if self.step_by_step_evaluation is None:
            self.step_by_step_evaluation = []