"""
Демонстрация работы системы бенчмарка
"""
import asyncio
from datetime import datetime
from typing import List

from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.solution_algorithm import SolutionAlgorithm
from domain.models.benchmark.solution_step import SolutionStep, StepType
from domain.models.benchmark.benchmark_result import BenchmarkResult
from domain.models.benchmark.benchmark_session import BenchmarkSession

from infrastructure.repositories.benchmark_repository_impl import BenchmarkRepositoryImpl
from infrastructure.services.text_similarity_service import TextSimilarityService
from infrastructure.adapters.data.benchmark_data_adapter import BenchmarkDataAdapter

from application.services.benchmark_runner_service import BenchmarkRunnerService
from application.orchestration.patterns.benchmark_execution_pattern import BenchmarkExecutionPattern
from application.services.deviation_detector import DeviationDetector
from application.services.solution_analyzer_service import SolutionAnalyzerService


class MockAgent:
    """
    Мок-агент для демонстрации работы системы бенчмарка
    """
    
    async def execute_task(self, task: str) -> str:
        """
        Выполнить задачу и вернуть ответ
        """
        # В реальной реализации здесь будет вызов настоящего агента
        # Для демонстрации возвращаем простой ответ
        if "как дела" in task.lower():
            return "У меня все хорошо, спасибо! А у вас как?"
        elif "погода" in task.lower():
            return "Сегодня солнечно и тепло. Температура около 22 градусов."
        elif "время" in task.lower():
            return f"Текущее время: {datetime.now().strftime('%H:%M:%S')}"
        elif "анализ" in task.lower() or "найди" in task.lower():
            # Имитация более сложного ответа
            return "Я проанализировал проект и нашел следующие ключевые компоненты: main.py, utils.py, config.py"
        else:
            return f"Я получил ваш запрос: '{task}'. Это интересный вопрос, требующий анализа."


async def create_sample_benchmarks(repository):
    """
    Создать примеры бенчмарков для демонстрации
    """
    # Создаем несколько примеров вопросов с эталонными ответами и алгоритмами решения
    questions = [
        BenchmarkQuestion(
            question_id="q1",
            question_text="Как дела?",
            expected_answer="Вежливый и позитивный ответ о самочувствии",
            solution_algorithm=SolutionAlgorithm(
                steps=[
                    SolutionStep(
                        step_number=1,
                        description="Понять эмоциональный тон вопроса",
                        expected_action="Анализ эмоционального окраса запроса",
                        expected_observation="Вопрос носит вежливый характер, ожидается вежливый ответ",
                        required_capability="emotion_analysis",
                        estimated_complexity=1
                    ),
                    SolutionStep(
                        step_number=2,
                        description="Сформировать позитивный ответ",
                        expected_action="Генерация вежливого и позитивного ответа",
                        expected_observation="Сгенерирован ответ с позитивным тоном",
                        required_capability="response_generation",
                        estimated_complexity=1
                    )
                ],
                required_skills=["EmotionAnalysisSkill", "ResponseGenerationSkill"],
                expected_tools=[],
                validation_criteria=["Тон ответа позитивный", "Ответ вежливый"]
            ),
            category="conversation",
            difficulty_level=1
        ),
        BenchmarkQuestion(
            question_id="q2",
            question_text="Какая сегодня погода?",
            expected_answer="Информация о текущей погоде",
            solution_algorithm=SolutionAlgorithm(
                steps=[
                    SolutionStep(
                        step_number=1,
                        description="Определить запрос информации о погоде",
                        expected_action="Распознавание намерения получить информацию о погоде",
                        expected_observation="Выявлено намерение пользователя получить информацию о погоде",
                        required_capability="intent_recognition",
                        estimated_complexity=1
                    ),
                    SolutionStep(
                        step_number=2,
                        description="Попытаться получить информацию о погоде",
                        expected_action="Поиск информации о погоде или генерация ответа",
                        expected_observation="Получена информация о погоде или сгенерирован разумный ответ",
                        required_capability="information_retrieval",
                        estimated_complexity=2
                    )
                ],
                required_skills=["IntentRecognitionSkill", "InformationRetrievalSkill"],
                expected_tools=[],
                validation_criteria=["Ответ содержит информацию о погоде", "Ответ разумный"]
            ),
            category="information",
            difficulty_level=2
        ),
        BenchmarkQuestion(
            question_id="q3",
            question_text="Найди все функции в проекте, которые используют SQL-запросы",
            expected_answer="Список функций, использующих SQL-запросы, с описанием их назначения",
            solution_algorithm=SolutionAlgorithm(
                steps=[
                    SolutionStep(
                        step_number=1,
                        description="Анализ структуры проекта",
                        expected_action="Использовать инструмент анализа файлов",
                        expected_observation="Получен список файлов с расширениями .py, .sql",
                        required_capability="code_analysis.file_discovery",
                        step_type=StepType.ANALYSIS,
                        required_skills=["CodeAnalysisSkill"],
                        expected_tools=["FileListerTool"]
                    ),
                    SolutionStep(
                        step_number=2,
                        description="Поиск функций с SQL-запросами",
                        expected_action="Применить инструмент поиска строк",
                        expected_observation="Найти файлы, содержащие ключевые слова SELECT, INSERT, UPDATE",
                        required_capability="code_analysis.pattern_matching",
                        step_type=StepType.DISCOVERY,
                        required_skills=["PatternMatchingSkill"],
                        expected_tools=["StringSearchTool"]
                    ),
                    SolutionStep(
                        step_number=3,
                        description="Анализ найденных функций",
                        expected_action="Анализ синтаксиса и семантики найденных функций",
                        expected_observation="Определены функции, использующие SQL-запросы, с описанием их назначения",
                        required_capability="code_analysis.semantic_analysis",
                        step_type=StepType.ANALYSIS,
                        required_skills=["SemanticAnalysisSkill"],
                        expected_tools=["CodeParserTool"]
                    ),
                    SolutionStep(
                        step_number=4,
                        description="Формирование отчета",
                        expected_action="Генерация списка функций с описанием",
                        expected_observation="Сформирован читаемый отчет с описанием найденных функций",
                        required_capability="report_generation",
                        step_type=StepType.SYNTHESIS,
                        required_skills=["ReportGenerationSkill"]
                    )
                ],
                required_skills=["CodeAnalysisSkill", "PatternMatchingSkill", "SemanticAnalysisSkill", "ReportGenerationSkill"],
                expected_tools=["FileListerTool", "StringSearchTool", "CodeParserTool"],
                validation_criteria=["Найдены все функции с SQL", "Классифицированы по типам запросов", "Описано назначение"]
            ),
            category="code_analysis",
            difficulty_level=3
        )
    ]
    
    # Сохраняем вопросы в репозиторий
    for question in questions:
        await repository.save_benchmark_question(question)
    
    print(f"Создано {len(questions)} примеров бенчмарков")


async def main():
    """
    Основная функция демонстрации
    """
    print("=== Демонстрация системы бенчмарка для проверки агента ===\n")
    
    # Создаем репозиторий
    repository = BenchmarkRepositoryImpl()
    
    # Создаем оценщик
    evaluator = TextSimilarityService()
    
    # Создаем сервис запуска бенчмарков
    benchmark_service = BenchmarkRunnerService(repository, evaluator)
    
    # Создаем паттерн выполнения бенчмарка
    benchmark_pattern = BenchmarkExecutionPattern(benchmark_service)
    
    # Создаем мок-агента
    agent = MockAgent()
    
    # Создаем примеры бенчмарков
    await create_sample_benchmarks(repository)
    
    print("\n=== Запуск бенчмарка ===")
    
    # Запускаем бенчмарк для категории conversation
    session, report = await benchmark_pattern.execute_benchmark_with_analysis(
        categories=["conversation", "information", "code_analysis"],
        agent=agent
    )
    
    print(f"\nСессия бенчмарка завершена:")
    print(f"- ID сессии: {session.session_id}")
    print(f"- Всего вопросов: {session.total_questions}")
    print(f"- Общий балл: {session.overall_score:.2f}")
    
    print(f"\n=== Отчет по бенчмарку ===")
    print(report)
    
    # Демонстрируем анализ решения
    print("\n=== Демонстрация анализа решения ===")
    
    analyzer = SolutionAnalyzerService()
    detector = DeviationDetector()
    
    # Имитируем шаги, которые мог бы сделать агент
    mock_agent_steps = [
        {"action": "Распознал вежливый вопрос о самочувствии", "used_tools": [], "used_skills": ["EmotionAnalysisSkill"], "status": "completed"},
        {"action": "Сгенерировал позитивный ответ", "used_tools": [], "used_skills": ["ResponseGenerationSkill"], "status": "completed"}
    ]
    
    # Загружаем один из вопросов для анализа
    question = await repository.get_benchmark_question("q1")
    
    if question:
        # Сравниваем пути решения
        comparison = await analyzer.compare_solution_paths(mock_agent_steps, question.solution_algorithm)
        
        print(f"Точность пути решения: {comparison['path_accuracy']:.2f}")
        print(f"Ожидаемые шаги: {comparison['total_expected_steps']}")
        print(f"Фактические шаги: {comparison['total_actual_steps']}")
        print(f"Завершенные шаги: {comparison['completed_steps']}")
        
        # Обнаружение отклонений
        deviations = analyzer.deviation_detector.detect_deviation_points(mock_agent_steps, question.solution_algorithm)
        print(f"Найдено отклонений: {len(deviations)}")
        
        if deviations:
            print("Точки отклонения:")
            for dev in deviations:
                print(f"  Шаг {dev['step_number']}: {dev['deviation_description']}")


if __name__ == "__main__":
    asyncio.run(main())