"""
Модель сессии бенчмарка
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from domain.models.benchmark.benchmark_result import BenchmarkResult


@dataclass
class BenchmarkSession:
    """
    Модель сессии бенчмарка
    """
    session_id: str
    benchmark_name: str
    start_time: datetime
    results: List[BenchmarkResult]
    end_time: Optional[datetime] = None
    overall_score: Optional[float] = None
    total_questions: int = 0
    questions_completed: int = 0
    
    def __post_init__(self):
        """Инициализация значений по умолчанию."""
        if self.end_time is None:
            self.end_time = datetime.now()
        if self.results is None:
            self.results = []
        if self.total_questions == 0 and self.results:
            self.total_questions = len(self.results)
        if self.questions_completed == 0:
            self.questions_completed = len(self.results)
    
    def calculate_overall_score(self) -> float:
        """Рассчитать общий балл сессии"""
        if not self.results:
            return 0.0
        total_score = sum(result.similarity_score for result in self.results)
        return total_score / len(self.results)
    
    def finalize_session(self) -> None:
        """Завершить сессию и рассчитать итоговые метрики"""
        self.end_time = datetime.now()
        self.overall_score = self.calculate_overall_score()