"""
Паттерн выполнения бенчмарка
"""
from typing import List, Any
from datetime import datetime

from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_session import BenchmarkSession
from application.services.benchmark_runner_service import BenchmarkRunnerService
from domain.agents.base_agent import BaseAgent


class BenchmarkExecutionPattern:
    """
    Паттерн выполнения бенчмарка
    """
    
    def __init__(self, benchmark_service: BenchmarkRunnerService):
        self.benchmark_service = benchmark_service
    
    async def execute_benchmark(
        self,
        categories: List[str],
        agent: BaseAgent,
        limit_per_category: int = None
    ) -> BenchmarkSession:
        """
        Выполнить бенчмарк по заданным категориям
        """
        all_questions = []
        
        # Загружаем вопросы из всех указанных категорий
        for category in categories:
            questions = await self.benchmark_service.load_questions(category)
            
            # Если указан лимит, ограничиваем количество вопросов
            if limit_per_category:
                questions = questions[:limit_per_category]
            
            all_questions.extend(questions)
        
        # Запускаем бенчмарк с собранными вопросами
        session = await self.benchmark_service.run_benchmark(all_questions, agent)
        
        return session
    
    async def execute_benchmark_with_analysis(
        self,
        categories: List[str],
        agent: BaseAgent,
        limit_per_category: int = None
    ) -> tuple[BenchmarkSession, str]:
        """
        Выполнить бенчмарк с анализом и получить сессию и отчет
        """
        session = await self.execute_benchmark(categories, agent, limit_per_category)
        report = await self.benchmark_service.generate_report(session)
        
        return session, report