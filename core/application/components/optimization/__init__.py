"""
Компоненты системы оптимизации промптов.

КОМПОНЕНТЫ:
- DatasetBuilder: построение датасета из логов и метрик (v1)
- DatasetBuilder (v2): построение датасета из execution traces
- ScenarioBuilder: классификация сценариев
- BenchmarkRunner: воспроизводимое тестирование
- Evaluator: оценка качества с системой метрик
- PromptGenerator: умная генерация промптов
- VersionManager: управление версиями промптов
- SafetyLayer: проверка на деградацию
- OptimizationOrchestrator: оркестрация цикла оптимизации (v1)
- OptimizationOrchestrator (v2): оркестрация с анализом traces
- TraceHandler: получение и реконструкция traces
- TraceCollector: сбор execution traces
- PatternAnalyzer: анализ паттернов выполнения
- PromptResponseAnalyzer: анализ промптов и ответов
- RootCauseAnalyzer: поиск корневых причин
- ExampleExtractor: извлечение примеров из traces
"""

from .dataset_builder import DatasetBuilder
from .dataset_builder_v2 import DatasetBuilder as DatasetBuilderV2
from .scenario_builder import ScenarioBuilder
from .benchmark_runner import BenchmarkRunner
from .evaluator import Evaluator
from .prompt_generator import PromptGenerator
from .version_manager import VersionManager
from .safety_layer import SafetyLayer
from .orchestrator import OptimizationOrchestrator
from .orchestrator_v2 import OptimizationOrchestrator as OptimizationOrchestratorV2
from .trace_handler import TraceHandler
from .trace_collector import TraceCollector
from .pattern_analyzer import PatternAnalyzer
from .prompt_analyzer import PromptResponseAnalyzer
from .root_cause_analyzer import RootCauseAnalyzer
from .example_extractor import ExampleExtractor

__all__ = [
    # v1 компоненты
    "DatasetBuilder",
    "ScenarioBuilder",
    "BenchmarkRunner",
    "Evaluator",
    "PromptGenerator",
    "VersionManager",
    "SafetyLayer",
    "OptimizationOrchestrator",
    # v2 компоненты
    "DatasetBuilderV2",
    "OptimizationOrchestratorV2",
    # Анализ traces
    "TraceHandler",
    "TraceCollector",
    "PatternAnalyzer",
    "PromptResponseAnalyzer",
    "RootCauseAnalyzer",
    "ExampleExtractor",
]
