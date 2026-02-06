"""
Абстрактный репозиторий для работы с бенчмарками
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult


class IBenchmarkRepository(ABC):
    """
    Абстрактный интерфейс репозитория для работы с бенчмарками
    """
    
    @abstractmethod
    async def save_benchmark_question(self, question: BenchmarkQuestion) -> bool:
        """
        Сохранить вопрос бенчмарка
        """
        pass
    
    @abstractmethod
    async def get_benchmark_question(self, question_id: str) -> Optional[BenchmarkQuestion]:
        """
        Получить вопрос бенчмарка по ID
        """
        pass
    
    @abstractmethod
    async def get_all_questions_by_category(self, category: str) -> List[BenchmarkQuestion]:
        """
        Получить все вопросы по категории
        """
        pass
    
    @abstractmethod
    async def get_all_questions(self) -> List[BenchmarkQuestion]:
        """
        Получить все вопросы
        """
        pass
    
    @abstractmethod
    async def save_benchmark_result(self, result: BenchmarkResult) -> bool:
        """
        Сохранить результат бенчмарка
        """
        pass
    
    @abstractmethod
    async def get_results_by_session(self, session_id: str) -> List[BenchmarkResult]:
        """
        Получить результаты по ID сессии
        """
        pass
    
    @abstractmethod
    async def get_results_by_question(self, question_id: str) -> List[BenchmarkResult]:
        """
        Получить результаты по ID вопроса
        """
        pass