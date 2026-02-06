"""
Сервис запуска бенчмарков
"""
from typing import List
import uuid
from datetime import datetime

from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult
from domain.models.benchmark.benchmark_session import BenchmarkSession
from domain.abstractions.benchmark_repository import IBenchmarkRepository
from domain.abstractions.benchmark_evaluator import IBenchmarkEvaluator
from domain.agents.base_agent import BaseAgent


class BenchmarkRunnerService:
    """
    Сервис запуска бенчмарков
    """
    
    def __init__(
        self,
        repository: IBenchmarkRepository,
        evaluator: IBenchmarkEvaluator
    ):
        self.repository = repository
        self.evaluator = evaluator
    
    async def load_questions(self, category: str) -> List[BenchmarkQuestion]:
        """
        Загрузить вопросы по категории
        """
        return await self.repository.get_all_questions_by_category(category)
    
    async def run_benchmark(
        self,
        questions: List[BenchmarkQuestion],
        agent: BaseAgent
    ) -> BenchmarkSession:
        """
        Запустить бенчмарк с заданными вопросами
        """
        session_id = str(uuid.uuid4())
        benchmark_name = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = BenchmarkSession(
            session_id=session_id,
            benchmark_name=benchmark_name,
            start_time=datetime.now(),
            results=[]
        )
        
        for question in questions:
            # Запускаем агента с вопросом
            agent_response = await self._run_agent_with_question(agent, question)
            
            # Оцениваем ответ
            result = await self.evaluator.evaluate_response(
                agent_response=agent_response,
                expected_answer=question.expected_answer,
                question=question
            )
            
            # Обновляем ID сессии в результате
            result.benchmark_id = session_id
            
            # Сохраняем результат
            await self.repository.save_benchmark_result(result)
            
            # Добавляем результат в сессию
            session.results.append(result)
        
        # Завершаем сессию
        session.finalize_session()
        
        return session
    
    async def generate_report(self, session: BenchmarkSession) -> str:
        """
        Сгенерировать отчет по сессии бенчмарка
        """
        report_lines = [
            f"Отчет по бенчмарку: {session.benchmark_name}",
            f"ID сессии: {session.session_id}",
            f"Дата начала: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Дата окончания: {session.end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Всего вопросов: {session.total_questions}",
            f"Общий балл: {session.overall_score:.2f}",
            "",
            "Детали по вопросам:"
        ]
        
        for i, result in enumerate(session.results, 1):
            report_lines.append(f"  {i}. Вопрос ID: {result.question_id}")
            report_lines.append(f"     Сходство: {result.similarity_score:.2f}")
            report_lines.append(f"     Метрики: {result.evaluation_metrics}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    async def _run_agent_with_question(self, agent: BaseAgent, question: BenchmarkQuestion) -> str:
        """
        Запустить агента с конкретным вопросом
        """
        # Временная реализация - в будущем может потребоваться более сложная логика
        # для передачи алгоритма решения в агент как эталон
        try:
            # Вызываем агента с вопросом
            response = await agent.execute_task(question.question_text)
            return str(response) if response else ""
        except Exception as e:
            # В случае ошибки возвращаем информацию об ошибке
            return f"Ошибка при выполнении задачи: {str(e)}"