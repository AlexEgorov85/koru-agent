"""
Фикстуры для системного контекста
"""
from application.context.system.system_context import SystemContext
from application.services.prompt_renderer import PromptRenderer
from application.services.benchmark_runner_service import BenchmarkRunnerService
from infrastructure.testing.llm.test_llm_provider import TestLLMProvider
from infrastructure.testing.db.in_memory_db_provider import InMemoryDBProvider
from infrastructure.services.prompt_storage.file_prompt_repository import FilePromptRepository, FileSnapshotManager
from infrastructure.repositories.benchmark_repository_impl import BenchmarkRepositoryImpl  # Используем реальный репозиторий
from domain.abstractions.benchmark_evaluator import IBenchmarkEvaluator
from application.services.solution_analyzer_service import SolutionAnalyzerService
from application.services.deviation_detector import DeviationDetector


def create_test_system_context() -> SystemContext:
    """
    Создать тестовый системный контекст с использованием централизованных моков
    """
    # Создаем централизованные моки
    llm_provider = TestLLMProvider()
    db_provider = InMemoryDBProvider()
    
    # Создаем репозитории с моками
    prompt_repository = FilePromptRepository()
    # Загружаем промты из файлов
    prompt_repository.load_from_directory("prompts")
    snapshot_manager = FileSnapshotManager()
    
    # Создаем реальные сервисы
    prompt_renderer = PromptRenderer(prompt_repository, snapshot_manager)
    
    # Создаем реальные зависимости для сервиса бенчмарков
    benchmark_repository = BenchmarkRepositoryImpl()  # Используем реальный репозиторий
    # Для оценщика также используем реальный класс, если он существует, или создаем простую реализацию
    # Если нет подходящего класса, можем создать тестовую реализацию
    from infrastructure.services.text_similarity_service import TextSimilarityService
    benchmark_evaluator = TextSimilarityService()
    
    benchmark_runner_service = BenchmarkRunnerService(
        repository=benchmark_repository,
        evaluator=benchmark_evaluator
    )
    
    # Создаем дополнительные сервисы
    solution_analyzer_service = SolutionAnalyzerService()
    deviation_detector = DeviationDetector()
    
    # Создаем системный контекст
    system_context = SystemContext()
    system_context.register_service("llm_provider", llm_provider)
    system_context.register_service("db_provider", db_provider)
    system_context.register_service("prompt_repository", prompt_repository)
    system_context.register_service("snapshot_manager", snapshot_manager)
    system_context.register_service("prompt_renderer", prompt_renderer)
    system_context.register_service("benchmark_runner_service", benchmark_runner_service)
    system_context.register_service("solution_analyzer_service", solution_analyzer_service)
    system_context.register_service("deviation_detector", deviation_detector)
    
    return system_context
