"""
Интерфейс для оценки ответов агента
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult


class IBenchmarkEvaluator(ABC):
    """
    Интерфейс для оценки ответов агента
    """
    
    @abstractmethod
    async def evaluate_response(
        self, 
        agent_response: str, 
        expected_answer: str,
        question: BenchmarkQuestion
    ) -> BenchmarkResult:
        """
        Оценить ответ агента
        """
        pass
    
    @abstractmethod
    async def calculate_similarity(
        self, 
        response1: str, 
        response2: str
    ) -> float:
        """
        Рассчитать схожесть двух ответов
        """
        pass
    
    @abstractmethod
    async def analyze_solution_path(
        self,
        actual_steps: Any,
        expected_algorithm: Any
    ) -> Dict[str, Any]:
        """
        Анализировать путь решения
        """
        pass