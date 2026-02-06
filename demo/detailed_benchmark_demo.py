"""
Подробная демонстрация работы системы бенчмарка
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

from application.services.benchmark_runner_service import BenchmarkRunnerService
from application.orchestration.patterns.benchmark_execution_pattern import BenchmarkExecutionPattern
from application.services.deviation_detector import DeviationDetector
from application.services.solution_analyzer_service import SolutionAnalyzerService


class DetailedMockAgent:
    """
    Мок-агент с более подробной информацией о шагах
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

    def get_execution_steps(self, task: str) -> List[dict]:
        """
        Возвращает шаги выполнения задачи (для демонстрации анализа пути решения)
        """
        if "как дела" in task.lower():
            return [
                {"action": "Распознавание эмоционального окраса запроса", "used_tools": [], "used_skills": ["EmotionAnalysisSkill"], "status": "completed"},
                {"action": "Генерация вежливого и позитивного ответа", "used_tools": [], "used_skills": ["ResponseGenerationSkill"], "status": "completed"}
            ]
        elif "погода" in task.lower():
            return [
                {"action": "Распознавание намерения получить информацию о погоде", "used_tools": [], "used_skills": ["IntentRecognitionSkill"], "status": "completed"},
                {"action": "Поиск информации о погоде или генерация ответа", "used_tools": [], "used_skills": ["InformationRetrievalSkill"], "status": "completed"}
            ]
        elif "анализ" in task.lower() or "найди" in task.lower():
            return [
                {"action": "Анализ структуры проекта", "used_tools": ["FileListerTool"], "used_skills": ["CodeAnalysisSkill"], "status": "completed"},
                {"action": "Поиск функций с SQL-запросами", "used_tools": ["StringSearchTool"], "used_skills": ["PatternMatchingSkill"], "status": "completed"},
                {"action": "Анализ найденных функций", "used_tools": ["CodeParserTool"], "used_skills": ["SemanticAnalysisSkill"], "status": "completed"},
                {"action": "Формирование отчета", "used_tools": [], "used_skills": ["ReportGenerationSkill"], "status": "completed"}
            ]
        else:
            return [
                {"action": "Анализ запроса пользователя", "used_tools": [], "used_skills": ["BasicAnalysisSkill"], "status": "completed"},
                {"action": "Формирование ответа", "used_tools": [], "used_skills": ["ResponseGenerationSkill"], "status": "completed"}
            ]


async def create_detailed_benchmarks(repository):
    """
    Создать подробные примеры бенчмарков для демонстрации
    """
    # Создаем примеры вопросов с эталонными ответами и детализированными алгоритмами решения
    questions = [
        BenchmarkQuestion(
            question_id="detailed_q1",
            question_text="Проведи анализ структуры проекта и предоставь отчет",
            expected_answer="Детальный отчет о структуре проекта с описанием ключевых компонентов",
            solution_algorithm=SolutionAlgorithm(
                steps=[
                    SolutionStep(
                        step_number=1,
                        description="Анализ структуры проекта",
                        expected_action="Использовать инструмент анализа файлов",
                        expected_observation="Получен список файлов и директорий проекта",
                        required_capability="code_analysis.structure_analysis",
                        step_type=StepType.ANALYSIS,
                        required_skills=["StructureAnalysisSkill"],
                        expected_tools=["FileListerTool"],
                        estimated_complexity=2
                    ),
                    SolutionStep(
                        step_number=2,
                        description="Идентификация ключевых компонентов",
                        expected_action="Анализ файлов для выявления основных компонентов",
                        expected_observation="Определены ключевые файлы и модули проекта",
                        required_capability="code_analysis.component_identification",
                        step_type=StepType.DISCOVERY,
                        required_skills=["ComponentIdentificationSkill"],
                        expected_tools=["FileReaderTool"],
                        estimated_complexity=3
                    ),
                    SolutionStep(
                        step_number=3,
                        description="Формирование отчета",
                        expected_action="Генерация структурированного отчета",
                        expected_observation="Создан читаемый отчет о структуре проекта",
                        required_capability="report_generation",
                        step_type=StepType.SYNTHESIS,
                        required_skills=["ReportGenerationSkill"],
                        expected_tools=[],
                        estimated_complexity=2
                    )
                ],
                required_skills=["StructureAnalysisSkill", "ComponentIdentificationSkill", "ReportGenerationSkill"],
                expected_tools=["FileListerTool", "FileReaderTool"],
                validation_criteria=["Найдена структура проекта", "Выделены ключевые компоненты", "Сформирован читаемый отчет"],
                description="Алгоритм анализа структуры проекта"
            ),
            category="detailed_analysis",
            difficulty_level=3
        )
    ]
    
    # Сохраняем вопросы в репозиторий
    for question in questions:
        await repository.save_benchmark_question(question)
    
    print(f"Создано {len(questions)} подробных примеров бенчмарков")


async def main():
    """
    Основная функция подробной демонстрации
    """
    print("=== Подробная демонстрация системы бенчмарка ===\n")
    
    # Создаем репозиторий
    repository = BenchmarkRepositoryImpl()
    
    # Создаем оценщик
    evaluator = TextSimilarityService()
    
    # Создаем сервис запуска бенчмарков
    benchmark_service = BenchmarkRunnerService(repository, evaluator)
    
    # Создаем паттерн выполнения бенчмарка
    benchmark_pattern = BenchmarkExecutionPattern(benchmark_service)
    
    # Создаем мок-агента с детализацией шагов
    agent = DetailedMockAgent()
    
    # Создаем подробные примеры бенчмарков
    await create_detailed_benchmarks(repository)
    
    print("\n=== Загрузка и анализ созданного бенчмарка ===")
    
    # Загружаем созданный бенчмарк
    question = await repository.get_benchmark_question("detailed_q1")
    
    if question:
        print(f"Вопрос: {question.question_text}")
        print(f"Категория: {question.category}")
        print(f"Уровень сложности: {question.difficulty_level}")
        print(f"Ожидаемый ответ: {question.expected_answer}")
        print(f"Количество шагов в алгоритме: {len(question.solution_algorithm.steps)}")
        
        print("\nШаги алгоритма решения:")
        for step in question.solution_algorithm.steps:
            print(f"  {step.step_number}. {step.description}")
            print(f"     Ожидаемое действие: {step.expected_action}")
            print(f"     Требуемые навыки: {step.required_skills}")
            print(f"     Ожидаемые инструменты: {step.expected_tools}")
            print(f"     Тип шага: {step.step_type}")
            print(f"     Сложность: {step.estimated_complexity}")
    
    print("\n=== Демонстрация анализа решения ===")
    
    # Создаем сервисы анализа
    analyzer = SolutionAnalyzerService()
    detector = DeviationDetector()
    
    # Используем мок-агент для получения шагов выполнения
    task = "Проведи анализ структуры проекта и предоставь отчет"
    agent_steps = agent.get_execution_steps(task)
    
    print("Шаги, выполненные агентом:")
    for i, step in enumerate(agent_steps, 1):
        print(f"  {i}. {step['action']}")
        print(f"     Использованные навыки: {step['used_skills']}")
        print(f"     Использованные инструменты: {step['used_tools']}")
    
    if question:
        print("\n=== Сравнение путей решения ===")
        
        # Сравниваем пути решения
        comparison = await analyzer.compare_solution_paths(agent_steps, question.solution_algorithm)
        
        print(f"Точность пути решения: {comparison['path_accuracy']:.2f}")
        print(f"Ожидаемые шаги: {comparison['total_expected_steps']}")
        print(f"Фактические шаги: {comparison['total_actual_steps']}")
        print(f"Завершенные шаги: {comparison['completed_steps']}")
        print(f"Коэффициент эффективности: {comparison['efficiency_ratio']:.2f}")
        
        # Обнаружение отклонений
        deviations = analyzer.deviation_detector.detect_deviation_points(agent_steps, question.solution_algorithm)
        print(f"\nНайдено отклонений: {len(deviations)}")
        
        if deviations:
            print("Точки отклонения:")
            for dev in deviations:
                print(f"  Шаг {dev['step_number']}: {dev['deviation_description']}")
                print(f"     Тип отклонения: {dev['deviation_type']}")
                print(f"     Серьезность: {dev['deviation_severity']}")
        
        # Анализ влияния отклонений
        impact_analysis = analyzer.deviation_detector.analyze_deviation_impact(deviations)
        print(f"\nАнализ влияния отклонений:")
        print(f"  Всего отклонений: {impact_analysis['total_deviations']}")
        print(f"  Структурные отклонения: {impact_analysis['structural_deviations']}")
        print(f"  Логические отклонения: {impact_analysis['logical_deviations']}")
        print(f"  Технические отклонения: {impact_analysis['technical_deviations']}")
        print(f"  Отклонения высокой серьезности: {impact_analysis['high_severity_deviations']}")
        print(f"  Оценка риска: {impact_analysis['risk_score']:.2f}")
        print(f"  Оценка влияния: {impact_analysis['impact_assessment']}")
    
    print("\n=== Демонстрация оценки ответа ===")
    
    # Получаем ответ от агента
    agent_response = await agent.execute_task(task)
    print(f"Ответ агента: {agent_response}")
    print(f"Ожидаемый ответ: {question.expected_answer if question else 'N/A'}")
    
    # Оцениваем ответ
    if question:
        result = await evaluator.evaluate_response(
            agent_response=agent_response,
            expected_answer=question.expected_answer,
            question=question
        )
        
        print(f"Оценка схожести: {result.similarity_score:.2f}")
        print(f"Метрики оценки: {result.evaluation_metrics}")


if __name__ == "__main__":
    asyncio.run(main())