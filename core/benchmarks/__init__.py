"""
Бенчмарки для оценки качества агента.

КОМПОНЕНТЫ:
- benchmark_models: модели данных (BenchmarkScenario, BenchmarkResult, etc.)
- benchmark_validator: валидация результатов бенчмарков
- benchmark_runner: запуск бенчмарков
- benchmark_data_loader: загрузка данных для бенчмарков
- generate_agent_benchmark: генерация бенчмарков
- compare_benchmarks: сравнение результатов

Использование:
    from core.benchmarks import BenchmarkValidator, BenchmarkRunner
    validator = BenchmarkValidator()
"""
from core.benchmarks.benchmark_models import (
    # Модели оценки
    EvaluationType,
    EvaluationCriterion,
    CriterionScore,
    # Модели сценариев
    ExpectedOutput,
    ActualOutput,
    BenchmarkScenario,
    # Модели результатов
    BenchmarkResult,
    AccuracyEvaluation,
    VersionComparison,
    # Модели анализа
    FailureAnalysis,
    OptimizationMode,
    TargetMetric,
    OptimizationResult,
    # Модели логов
    LogType,
    LogEntry,
    # Модели оптимизации
    ScenarioType,
    MutationType,
    OptimizationSample,
    PromptVersion,
    EvaluationResult,
    BenchmarkDataset,
    BenchmarkRunResult,
)

from core.benchmarks.benchmark_validator import (
    SQLValidator,
    AnswerValidator,
    BenchmarkValidator,
)

from core.benchmarks.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkRunConfig,
)

from core.benchmarks.benchmark_data_loader import (
    BenchmarkDataLoader,
)

__all__ = [
    # Модели данных
    'EvaluationType',
    'EvaluationCriterion',
    'CriterionScore',
    'ExpectedOutput',
    'ActualOutput',
    'BenchmarkScenario',
    'BenchmarkResult',
    'AccuracyEvaluation',
    'VersionComparison',
    'FailureAnalysis',
    'OptimizationMode',
    'TargetMetric',
    'OptimizationResult',
    'LogType',
    'LogEntry',
    'ScenarioType',
    'MutationType',
    'OptimizationSample',
    'PromptVersion',
    'EvaluationResult',
    'BenchmarkDataset',
    'BenchmarkRunResult',
    # Валидатор
    'SQLValidator',
    'AnswerValidator',
    'BenchmarkValidator',
    # Раннер
    'BenchmarkRunner',
    'BenchmarkRunConfig',
    # Загрузчик
    'BenchmarkDataLoader',
]
