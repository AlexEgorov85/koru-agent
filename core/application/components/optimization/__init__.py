"""
Компоненты системы оптимизации промптов.

КОМПОНЕНТЫ:
- DatasetBuilder: построение датасета из логов и метрик
- ScenarioBuilder: классификация сценариев
- BenchmarkRunner: воспроизводимое тестирование
- Evaluator: оценка качества с системой метрик
- PromptGenerator: умная генерация промптов
- VersionManager: управление версиями промптов
- SafetyLayer: проверка на деградацию
- OptimizationOrchestrator: оркестрация цикла оптимизации
- TraceHandler: получение и реконструкция traces
- TraceCollector: сбор execution traces
- PatternAnalyzer: анализ паттернов выполнения
- PromptResponseAnalyzer: анализ промптов и ответов
- RootCauseAnalyzer: поиск корневых причин
"""

from .dataset_builder import DatasetBuilder
from .scenario_builder import ScenarioBuilder
from .benchmark_runner import BenchmarkRunner
from .evaluator import Evaluator
from .prompt_generator import PromptGenerator
from .version_manager import VersionManager
from .safety_layer import SafetyLayer
from .orchestrator import OptimizationOrchestrator
from .trace_handler import TraceHandler
from .trace_collector import TraceCollector
from .pattern_analyzer import PatternAnalyzer
from .prompt_analyzer import PromptResponseAnalyzer
from .root_cause_analyzer import RootCauseAnalyzer

__all__ = [
    "DatasetBuilder",
    "ScenarioBuilder",
    "BenchmarkRunner",
    "Evaluator",
    "PromptGenerator",
    "VersionManager",
    "SafetyLayer",
    "OptimizationOrchestrator",
    "TraceHandler",
    "TraceCollector",
    "PatternAnalyzer",
    "PromptResponseAnalyzer",
    "RootCauseAnalyzer",
]
