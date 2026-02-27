"""
Модели данных для системы бенчмарков и обучения.

КОМПОНЕНТЫ:
- EvaluationType: типы оценки
- EvaluationCriterion: критерий оценки
- BenchmarkScenario: сценарий бенчмарка
- ExpectedOutput: ожидаемый вывод
- ActualOutput: фактический вывод
- BenchmarkResult: результат бенчмарка
- AccuracyEvaluation: оценка точности
- CriterionScore: оценка по критерию
- VersionComparison: сравнение версий
- FailureAnalysis: анализ неудач
- TargetMetric: целевая метрика
- OptimizationMode: режим оптимизации
- OptimizationResult: результат оптимизации
- LogType: типы логов
- LogEntry: запись лога
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


# ============================================================================
# Модели оценки
# ============================================================================

class EvaluationType(Enum):
    """
    Типы оценки в бенчмарках.

    TYPES:
    - EXACT_MATCH: точное совпадение
    - SEMANTIC: семантическое сходство
    - COVERAGE: полнота покрытия
    - CUSTOM: пользовательская оценка
    """
    EXACT_MATCH = "exact_match"
    SEMANTIC = "semantic"
    COVERAGE = "coverage"
    CUSTOM = "custom"


@dataclass
class EvaluationCriterion:
    """
    Критерий оценки результата.

    ATTRIBUTES:
    - name: название критерия
    - evaluation_type: тип оценки
    - weight: вес критерия (0.0-1.0)
    - description: описание критерия
    - threshold: пороговое значение для прохождения
    """
    name: str
    evaluation_type: EvaluationType
    weight: float = 1.0
    description: str = ""
    threshold: float = 0.8

    def __post_init__(self):
        """Валидация веса"""
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Вес критерия должен быть от 0.0 до 1.0, получено {self.weight}")


@dataclass
class CriterionScore:
    """
    Оценка по отдельному критерию.

    ATTRIBUTES:
    - criterion: критерий оценки
    - score: полученная оценка (0.0-1.0)
    - passed: пройдено ли пороговое значение
    - details: детали оценки
    """
    criterion: EvaluationCriterion
    score: float
    passed: bool = True
    details: str = ""

    def __post_init__(self):
        """Валидация оценки"""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Оценка должна быть от 0.0 до 1.0, получено {self.score}")
        self.passed = self.score >= self.criterion.threshold


# ============================================================================
# Модели сценариев бенчмарка
# ============================================================================

@dataclass
class ExpectedOutput:
    """
    Ожидаемый вывод для бенчмарка.

    ATTRIBUTES:
    - content: ожидаемое содержимое
    - schema: JSON схема для валидации (опционально)
    - criteria: критерии оценки
    - metadata: дополнительные метаданные
    """
    content: Any
    schema: Optional[Dict[str, Any]] = None
    criteria: List[EvaluationCriterion] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_criterion(self, criterion: EvaluationCriterion) -> None:
        """Добавление критерия оценки"""
        self.criteria.append(criterion)


@dataclass
class ActualOutput:
    """
    Фактический вывод агента.

    ATTRIBUTES:
    - content: фактическое содержимое
    - execution_time_ms: время выполнения
    - tokens_used: количество использованных токенов
    - metadata: дополнительные метаданные
    """
    content: Any
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkScenario:
    """
    Сценарий бенчмарка для оценки качества агента.

    ATTRIBUTES:
    - id: идентификатор сценария
    - name: название сценария
    - description: описание сценария
    - goal: цель сценария (запрос к агенту)
    - expected_output: ожидаемый вывод
    - criteria: критерии оценки
    - timeout_seconds: таймаут выполнения
    - metadata: дополнительные метаданные
    """
    id: str
    name: str
    description: str
    goal: str
    expected_output: ExpectedOutput
    criteria: List[EvaluationCriterion] = field(default_factory=list)
    timeout_seconds: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Валидация сценария"""
        if not self.id:
            raise ValueError("ID сценария не может быть пустым")
        if not self.goal:
            raise ValueError("Цель сценария не может быть пустой")

    def add_criterion(self, criterion: EvaluationCriterion) -> None:
        """Добавление критерия оценки"""
        self.criteria.append(criterion)
        self.expected_output.add_criterion(criterion)


# ============================================================================
# Модели результатов бенчмарка
# ============================================================================

@dataclass
class BenchmarkResult:
    """
    Результат выполнения бенчмарка.

    ATTRIBUTES:
    - scenario_id: идентификатор сценария
    - versions: тестируемые версии {capability: version}
    - success: успешность выполнения
    - scores: оценки по критериям
    - overall_score: общая оценка
    - actual_output: фактический вывод
    - execution_time_ms: время выполнения
    - tokens_used: количество токенов
    - error: ошибка (если была)
    - timestamp: время выполнения
    - metadata: дополнительные метаданные
    """
    scenario_id: str
    versions: Dict[str, str]
    success: bool = False
    scores: List[CriterionScore] = field(default_factory=list)
    overall_score: float = 0.0
    actual_output: Optional[ActualOutput] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_overall_score(self) -> float:
        """
        Расчёт общей оценки на основе взвешенных критериев.

        RETURNS:
        - float: общая оценка (0.0-1.0)
        """
        if not self.scores:
            return 0.0

        total_weight = sum(score.criterion.weight for score in self.scores)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            score.score * score.criterion.weight
            for score in self.scores
        )

        self.overall_score = weighted_sum / total_weight
        return self.overall_score

    def all_criteria_passed(self) -> bool:
        """Проверка прохождения всех критериев"""
        return all(score.passed for score in self.scores)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'scenario_id': self.scenario_id,
            'versions': self.versions,
            'success': self.success,
            'scores': [
                {
                    'criterion': score.criterion.name,
                    'score': score.score,
                    'passed': score.passed,
                    'details': score.details
                }
                for score in self.scores
            ],
            'overall_score': self.overall_score,
            'execution_time_ms': self.execution_time_ms,
            'tokens_used': self.tokens_used,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class AccuracyEvaluation:
    """
    Оценка точности выполнения бенчмарка.

    ATTRIBUTES:
    - scenario_id: идентификатор сценария
    - total_runs: общее количество запусков
    - successful_runs: количество успешных запусков
    - accuracy: точность (successful_runs / total_runs)
    - scores_by_criterion: оценки по каждому критерию
    - avg_execution_time_ms: среднее время выполнения
    - avg_tokens_used: среднее количество токенов
    - timestamp: время оценки
    """
    scenario_id: str
    total_runs: int = 0
    successful_runs: int = 0
    accuracy: float = 0.0
    scores_by_criterion: Dict[str, List[float]] = field(default_factory=dict)
    avg_execution_time_ms: float = 0.0
    avg_tokens_used: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_results(cls, scenario_id: str, results: List[BenchmarkResult]) -> 'AccuracyEvaluation':
        """
        Создание оценки точности из списка результатов.

        ARGS:
        - scenario_id: идентификатор сценария
        - results: список результатов бенчмарка

        RETURNS:
        - AccuracyEvaluation: оценка точности
        """
        if not results:
            return cls(scenario_id=scenario_id)

        total_runs = len(results)
        successful_runs = sum(1 for r in results if r.success)
        accuracy = successful_runs / total_runs if total_runs > 0 else 0.0

        # Сбор оценок по критериям
        scores_by_criterion: Dict[str, List[float]] = {}
        for result in results:
            for score in result.scores:
                criterion_name = score.criterion.name
                if criterion_name not in scores_by_criterion:
                    scores_by_criterion[criterion_name] = []
                scores_by_criterion[criterion_name].append(score.score)

        # Среднее время выполнения
        avg_execution_time = sum(r.execution_time_ms for r in results) / total_runs

        # Среднее количество токенов
        avg_tokens = sum(r.tokens_used for r in results) / total_runs

        return cls(
            scenario_id=scenario_id,
            total_runs=total_runs,
            successful_runs=successful_runs,
            accuracy=accuracy,
            scores_by_criterion=scores_by_criterion,
            avg_execution_time_ms=avg_execution_time,
            avg_tokens_used=avg_tokens,
            timestamp=datetime.now()
        )


@dataclass
class VersionComparison:
    """
    Сравнение двух версий промпта/контракта.

    ATTRIBUTES:
    - capability: название способности
    - version_a: первая версия
    - version_b: вторая версия
    - metrics_a: метрики первой версии
    - metrics_b: метрики второй версии
    - winner: версия-победитель
    - improvement: улучшение в процентах
    - statistically_significant: статистическая значимость
    - details: детали сравнения
    """
    capability: str
    version_a: str
    version_b: str
    metrics_a: Dict[str, float]
    metrics_b: Dict[str, float]
    winner: Optional[str] = None
    improvement: float = 0.0
    statistically_significant: bool = False
    details: str = ""

    def calculate_improvement(self, metric: str = 'accuracy') -> float:
        """
        Расчёт улучшения между версиями.

        ARGS:
        - metric: имя метрики для сравнения

        RETURNS:
        - float: улучшение в процентах
        """
        value_a = self.metrics_a.get(metric, 0.0)
        value_b = self.metrics_b.get(metric, 0.0)

        if value_a == 0:
            self.improvement = 100.0 if value_b > 0 else 0.0
        else:
            self.improvement = ((value_b - value_a) / value_a) * 100

        # Определение победителя
        if value_b > value_a:
            self.winner = self.version_b
        elif value_a > value_b:
            self.winner = self.version_a
        else:
            self.winner = None

        return self.improvement


# ============================================================================
# Модели анализа и оптимизации
# ============================================================================

@dataclass
class FailureAnalysis:
    """
    Анализ неудач выполнения агента.

    ATTRIBUTES:
    - capability: название способности
    - version: версия промпта/контракта
    - total_failures: общее количество неудач
    - failure_categories: категории ошибок
    - common_patterns: распространённые паттерны ошибок
    - recommendations: рекомендации по улучшению
    - sample_errors: примеры ошибок
    - timestamp: время анализа
    """
    capability: str
    version: str
    total_failures: int = 0
    failure_categories: Dict[str, int] = field(default_factory=dict)
    common_patterns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    sample_errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_failure_category(self, category: str, count: int = 1) -> None:
        """Добавление категории ошибки"""
        self.failure_categories[category] = self.failure_categories.get(category, 0) + count
        self.total_failures += count

    def add_pattern(self, pattern: str) -> None:
        """Добавление паттерна ошибки"""
        if pattern not in self.common_patterns:
            self.common_patterns.append(pattern)

    def add_recommendation(self, recommendation: str) -> None:
        """Добавление рекомендации"""
        if recommendation not in self.recommendations:
            self.recommendations.append(recommendation)

    def get_top_failure_categories(self, limit: int = 5) -> List[tuple]:
        """Получение топ категорий ошибок"""
        sorted_categories = sorted(
            self.failure_categories.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_categories[:limit]


class OptimizationMode(Enum):
    """
    Режимы оптимизации.

    MODES:
    - ACCURACY: оптимизация точности
    - SPEED: оптимизация скорости
    - TOKENS: оптимизация использования токенов
    - BALANCED: сбалансированная оптимизация
    """
    ACCURACY = "accuracy"
    SPEED = "speed"
    TOKENS = "tokens"
    BALANCED = "balanced"


@dataclass
class TargetMetric:
    """
    Целевая метрика для оптимизации.

    ATTRIBUTES:
    - name: название метрики
    - target_value: целевое значение
    - current_value: текущее значение
    - threshold: минимально допустимое значение
    - weight: вес метрики в общей оптимизации
    """
    name: str
    target_value: float
    current_value: float = 0.0
    threshold: float = 0.0
    weight: float = 1.0

    def is_achieved(self) -> bool:
        """Проверка достижения целевого значения"""
        return self.current_value >= self.target_value

    def progress(self) -> float:
        """Прогресс достижения цели (0.0-1.0)"""
        if self.target_value == 0:
            return 1.0 if self.current_value >= 0 else 0.0
        return min(1.0, self.current_value / self.target_value)


@dataclass
class OptimizationResult:
    """
    Результат цикла оптимизации.

    ATTRIBUTES:
    - capability: название способности
    - from_version: начальная версия
    - to_version: конечная версия
    - mode: режим оптимизации
    - iterations: количество итераций
    - initial_metrics: начальные метрики
    - final_metrics: конечные метрики
    - improvements: улучшения по метрикам
    - target_achieved: достигнута ли цель
    - failure_analysis: анализ неудач
    - recommendations: рекомендации
    - timestamp: время завершения
    """
    capability: str
    from_version: str
    to_version: str
    mode: OptimizationMode
    iterations: int = 0
    initial_metrics: Dict[str, float] = field(default_factory=dict)
    final_metrics: Dict[str, float] = field(default_factory=dict)
    improvements: Dict[str, float] = field(default_factory=dict)
    target_achieved: bool = False
    failure_analysis: Optional[FailureAnalysis] = None
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def calculate_improvements(self) -> Dict[str, float]:
        """
        Расчёт улучшений по метрикам.

        RETURNS:
        - Dict[str, float]: улучшения по каждой метрике
        """
        for metric, initial_value in self.initial_metrics.items():
            final_value = self.final_metrics.get(metric, 0.0)
            if initial_value > 0:
                self.improvements[metric] = ((final_value - initial_value) / initial_value) * 100
            else:
                self.improvements[metric] = 100.0 if final_value > 0 else 0.0
        return self.improvements

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'capability': self.capability,
            'from_version': self.from_version,
            'to_version': self.to_version,
            'mode': self.mode.value,
            'iterations': self.iterations,
            'initial_metrics': self.initial_metrics,
            'final_metrics': self.final_metrics,
            'improvements': self.improvements,
            'target_achieved': self.target_achieved,
            'recommendations': self.recommendations,
            'timestamp': self.timestamp.isoformat()
        }


# ============================================================================
# Модели логов
# ============================================================================

class LogType(Enum):
    """
    Типы логов для обучения.

    TYPES:
    - CAPABILITY_SELECTION: выбор способности
    - ERROR: ошибка выполнения
    - BENCHMARK: событие бенчмарка
    - OPTIMIZATION: событие оптимизации
    - LLM_PROMPT: сгенерированный промпт для LLM
    - LLM_RESPONSE: полученный ответ от LLM
    """
    CAPABILITY_SELECTION = "capability_selection"
    ERROR = "error"
    BENCHMARK = "benchmark"
    OPTIMIZATION = "optimization"
    LLM_PROMPT = "llm_prompt"
    LLM_RESPONSE = "llm_response"


@dataclass
class LogEntry:
    """
    Запись структурированного лога.

    ATTRIBUTES:
    - timestamp: время записи
    - agent_id: идентификатор агента
    - session_id: идентификатор сессии
    - log_type: тип лога
    - data: данные лога
    - correlation_id: идентификатор корреляции
    - capability: название способности (опционально)
    - version: версия (опционально)
    - execution_context: контекст выполнения (опционально)
    - step_quality_score: оценка качества шага 0.0-1.0 (опционально)
    - benchmark_scenario_id: ID сценария бенчмарка (опционально)
    """
    timestamp: datetime
    agent_id: str
    session_id: str
    log_type: LogType
    data: Dict[str, Any]
    correlation_id: str = ""
    capability: Optional[str] = None
    version: Optional[str] = None
    execution_context: Optional[Dict[str, Any]] = None
    step_quality_score: Optional[float] = None
    benchmark_scenario_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'agent_id': self.agent_id,
            'session_id': self.session_id,
            'log_type': self.log_type.value,
            'data': self.data,
            'correlation_id': self.correlation_id,
            'capability': self.capability,
            'version': self.version,
            'execution_context': self.execution_context,
            'step_quality_score': self.step_quality_score,
            'benchmark_scenario_id': self.benchmark_scenario_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """Десериализация из словаря"""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            agent_id=data['agent_id'],
            session_id=data['session_id'],
            log_type=LogType(data['log_type']),
            data=data['data'],
            correlation_id=data.get('correlation_id', ''),
            capability=data.get('capability'),
            version=data.get('version'),
            execution_context=data.get('execution_context'),
            step_quality_score=data.get('step_quality_score'),
            benchmark_scenario_id=data.get('benchmark_scenario_id')
        )
