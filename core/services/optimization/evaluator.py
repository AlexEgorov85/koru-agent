"""
Evaluator - система оценки качества промптов.

ОТВЕТСТВЕННОСТЬ:
- Расчёт метрик качества (≥4 метрик)
- Вычисление итогового score
- Сравнение версий
- Селекция лучшей версии
"""
import logging
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from core.components.benchmarks.benchmark_models import (
    EvaluationResult,
    PromptVersion,
    BenchmarkRunResult,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure.event_bus.unified_event_bus import EventType

if TYPE_CHECKING:
    from core.infrastructure.logging.session import LoggingSession


@dataclass
class EvaluationConfig:
    """Конфигурация Evaluator"""
    # Веса метрик для расчёта score (SQL-задачи)
    success_rate_weight: float = 0.4
    execution_success_weight: float = 0.3
    sql_validity_weight: float = 0.2
    latency_weight: float = 0.1

    # Веса метрик для check_result
    validation_score_weight: float = 0.5  # Основной показатель качества
    script_accuracy_weight: float = 0.3   # Правильность выбора скрипта/параметров
    result_completeness_weight: float = 0.2  # Полнота результатов

    # Пороги
    min_success_rate: float = 0.8
    max_latency_ms: float = 1000.0


class Evaluator:
    """
    Система оценки качества промптов.

    RESPONSIBILITIES:
    - Расчёт метрик из результатов бенчмарка
    - Вычисление итогового score по формуле
    - Сравнение версий по метрикам
    - Селекция лучшей версии

    FORMULA:
    score = (
        success_rate * 0.4 +
        execution_success * 0.3 +
        sql_validity * 0.2 -
        latency * 0.1
    )

    USAGE:
    ```python
    evaluator = Evaluator(event_bus)
    result = evaluator.evaluate(version_id, benchmark_results)
    best = evaluator.select_best(evaluated_versions)
    ```
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        config: Optional[EvaluationConfig] = None,
        log_session: Optional['LoggingSession'] = None
    ):
        """
        Инициализация Evaluator.

        ARGS:
        - event_bus: шина событий
        - config: конфигурация
        - log_session: сессия логирования
        """
        self.event_bus = event_bus
        self.config = config or EvaluationConfig()
        self._log_session = log_session

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.app_logger:
            return self._log_session.app_logger
        return logging.getLogger(__name__)

    def evaluate(
        self,
        version_id: str,
        results: List[BenchmarkRunResult]
    ) -> EvaluationResult:
        """
        Оценка качества версии по результатам бенчмарка.

        ARGS:
        - version_id: идентификатор версии
        - results: результаты бенчмарка

        RETURNS:
        - EvaluationResult: результат оценки
        """
        if not results:
            return EvaluationResult(version_id=version_id)

        # Проверяем есть ли check_result сценарии
        has_check_result = any(
            r.raw_result and r.raw_result.get('metadata', {}).get('level') == 'check_result'
            for r in results
            if r.raw_result
        )

        if has_check_result:
            # Оценка для check_result
            return self._evaluate_check_result(version_id, results)
        else:
            # Стандартная оценка (SQL tasks)
            return self._evaluate_standard(version_id, results)

    def _evaluate_standard(
        self,
        version_id: str,
        results: List[BenchmarkRunResult]
    ) -> EvaluationResult:
        """
        Стандартная оценка для SQL задач.

        ARGS:
        - version_id: идентификатор версии
        - results: результаты бенчмарка

        RETURNS:
        - EvaluationResult: результат оценки
        """
        # Расчёт метрик
        success_rate = self._calculate_success_rate(results)
        execution_success = self._calculate_execution_success(results)
        sql_validity = self._calculate_sql_validity(results)
        latency = self._calculate_avg_latency(results)
        error_rate = self._calculate_error_rate(results)

        # Создание результата
        evaluation = EvaluationResult(
            version_id=version_id,
            success_rate=success_rate,
            sql_validity=sql_validity,
            execution_success=execution_success,
            latency=latency,
            error_rate=error_rate
        )

        # Расчёт итогового score
        evaluation.calculate_score()

        return evaluation

    def _evaluate_check_result(
        self,
        version_id: str,
        results: List[BenchmarkRunResult]
    ) -> EvaluationResult:
        """
        Оценка для check_result задач.

        ИСПОЛЬЗУЕТ:
        - validation_score (из CheckResultValidator) как основной показатель
        - script_accuracy (правильность выбора скрипта)
        - result_completeness (наличие результатов)

        ARGS:
        - version_id: идентификатор версии
        - results: результаты бенчмарка

        RETURNS:
        - EvaluationResult: результат оценки
        """
        # Базовые метрики
        success_rate = self._calculate_success_rate(results)
        execution_success = self._calculate_execution_success(results)
        latency = self._calculate_avg_latency(results)
        error_rate = self._calculate_error_rate(results)

        # Специфичные метрики для check_result
        validation_score = self._calculate_avg_validation_score(results)
        script_accuracy = self._calculate_script_accuracy(results)
        result_completeness = self._calculate_result_completeness(results)

        # Для check_result sql_validity заменяем на validation_score
        sql_validity = validation_score

        # Создание результата
        evaluation = EvaluationResult(
            version_id=version_id,
            success_rate=success_rate,
            sql_validity=sql_validity,  # Здесь validation_score
            execution_success=execution_success,
            latency=latency,
            error_rate=error_rate
        )

        # Переопределяем score с учетом специфики check_result
        evaluation.score = self._calculate_check_result_score(
            success_rate,
            execution_success,
            validation_score,
            script_accuracy,
            result_completeness,
            latency
        )

        # Сохраняем дополнительные метрики
        evaluation.metadata = {
            'validation_score': validation_score,
            'script_accuracy': script_accuracy,
            'result_completeness': result_completeness,
            'evaluation_type': 'check_result'
        }

        return evaluation

    def _calculate_avg_validation_score(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт среднего validation score.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: средний validation score (0.0-1.0)
        """
        validation_scores = [
            r.validation_score
            for r in results
            if r.validation_score is not None
        ]
        
        if not validation_scores:
            # Fallback: используем success_rate
            return self._calculate_success_rate(results)
        
        return sum(validation_scores) / len(validation_scores)

    def _calculate_script_accuracy(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт точности выбора скрипта/метода.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: точность (0.0-1.0)
        """
        if not results:
            return 0.0

        accurate_count = 0
        for result in results:
            if result.validation_checks:
                # Проверяем script_name_match или аналогичные проверки
                script_checks = [
                    value for key, value in result.validation_checks.items()
                    if 'script' in key.lower() or 'method' in key.lower()
                ]
                if script_checks:
                    accurate_count += sum(script_checks) / len(script_checks)
                else:
                    # Fallback: считаем успешное выполнение как точность
                    accurate_count += 1.0 if result.success else 0.0
            else:
                # Fallback для не-check_result задач
                accurate_count += 1.0 if result.success else 0.0

        return accurate_count / len(results)

    def _calculate_result_completeness(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт полноты результатов.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: полнота (0.0-1.0)
        """
        if not results:
            return 0.0

        complete_count = 0
        for result in results:
            if result.validation_checks:
                # Проверяем наличие результатов
                completeness_checks = [
                    value for key, value in result.validation_checks.items()
                    if 'result' in key.lower() or 'completeness' in key.lower()
                ]
                if completeness_checks:
                    complete_count += sum(completeness_checks) / len(completeness_checks)
                else:
                    complete_count += 1.0 if result.success else 0.0
            else:
                complete_count += 1.0 if result.success else 0.0

        return complete_count / len(results)

    def _calculate_check_result_score(
        self,
        success_rate: float,
        execution_success: float,
        validation_score: float,
        script_accuracy: float,
        result_completeness: float,
        latency: float
    ) -> float:
        """
        Расчёт score для check_result задач.

        ФОРМУЛА:
        score = (
            validation_score * 0.5 +
            script_accuracy * 0.3 +
            result_completeness * 0.2 -
            latency_penalty * 0.1
        )

        ARGS:
        - success_rate: доля успешных выполнений
        - execution_success: выполнения без критических ошибок
        - validation_score: средний validation score
        - script_accuracy: точность выбора скрипта
        - result_completeness: полнота результатов
        - latency: среднее время (ms)

        RETURNS:
        - float: итоговый score (0.0-1.0)
        """
        latency_penalty = min(latency / 1000, 1.0) * self.config.latency_weight

        score = (
            validation_score * self.config.validation_score_weight +
            script_accuracy * self.config.script_accuracy_weight +
            result_completeness * self.config.result_completeness_weight -
            latency_penalty
        )

        # Ограничиваем范围 0.0-1.0
        return max(0.0, min(1.0, score))

    def _calculate_success_rate(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт доли успешных выполнений.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: success rate (0.0-1.0)
        """
        if not results:
            return 0.0
        
        successful = sum(1 for r in results if r.success)
        return successful / len(results)

    def _calculate_execution_success(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт доли выполнений без ошибок выполнения.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: execution success (0.0-1.0)
        """
        if not results:
            return 0.0
        
        # Execution success = выполнения без критических ошибок
        no_critical_errors = sum(
            1 for r in results 
            if not r.error or self._is_non_critical_error(r.error)
        )
        return no_critical_errors / len(results)

    def _is_non_critical_error(self, error: str) -> bool:
        """
        Проверка является ли ошибка некритической.

        ARGS:
        - error: текст ошибки

        RETURNS:
        - bool: True если ошибка некритическая
        """
        non_critical_keywords = [
            'timeout',
            'warning',
            'deprecated',
            'retry'
        ]
        error_lower = error.lower()
        return any(kw in error_lower for kw in non_critical_keywords)

    def _calculate_sql_validity(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт валидности SQL (если применимо).

        Для не-SQL задач возвращает 1.0.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: sql validity (0.0-1.0)
        """
        if not results:
            return 1.0  # По умолчанию считаем валидным

        # Проверка на SQL ошибки
        sql_error_keywords = [
            'syntax error',
            'sql',
            'query',
            'table',
            'column',
            'select',
            'insert',
            'update',
            'delete'
        ]

        sql_errors = 0
        for result in results:
            if result.error:
                error_lower = result.error.lower()
                if any(kw in error_lower for kw in sql_error_keywords):
                    sql_errors += 1

        return 1.0 - (sql_errors / len(results))

    def _calculate_avg_latency(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт среднего времени выполнения.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: avg latency (ms)
        """
        if not results:
            return 0.0
        
        total_latency = sum(r.execution_time_ms for r in results)
        return total_latency / len(results)

    def _calculate_error_rate(self, results: List[BenchmarkRunResult]) -> float:
        """
        Расчёт доли ошибок.

        ARGS:
        - results: результаты бенчмарка

        RETURNS:
        - float: error rate (0.0-1.0)
        """
        if not results:
            return 0.0
        
        errors = sum(1 for r in results if r.error)
        return errors / len(results)

    def select_best(
        self,
        evaluations: List[EvaluationResult]
    ) -> Optional[EvaluationResult]:
        """
        Селекция лучшей версии по score.

        ARGS:
        - evaluations: результаты оценки версий

        RETURNS:
        - Optional[EvaluationResult]: лучшая версия или None
        """
        if not evaluations:
            return None

        # Сортировка по score (убывание)
        sorted_evals = sorted(
            evaluations,
            key=lambda e: e.score,
            reverse=True
        )

        best = sorted_evals[0]

        return best

    def compare(
        self,
        evaluation_a: EvaluationResult,
        evaluation_b: EvaluationResult
    ) -> Tuple[str, Dict[str, float]]:
        """
        Сравнение двух оценок.

        ARGS:
        - evaluation_a: оценка версии A
        - evaluation_b: оценка версии B

        RETURNS:
        - Tuple[str, Dict[str, float]]: (победитель, улучшения по метрикам)
        """
        improvements = {}
        
        # Сравнение по метрикам
        metrics = [
            ('success_rate', evaluation_a.success_rate, evaluation_b.success_rate),
            ('execution_success', evaluation_a.execution_success, evaluation_b.execution_success),
            ('sql_validity', evaluation_a.sql_validity, evaluation_b.sql_validity),
            ('latency', evaluation_a.latency, evaluation_b.latency),
            ('error_rate', evaluation_a.error_rate, evaluation_b.error_rate),
            ('score', evaluation_a.score, evaluation_b.score)
        ]

        for name, val_a, val_b in metrics:
            if name == 'latency' or name == 'error_rate':
                # Для latency и error_rate меньше = лучше
                diff = val_a - val_b
                improvements[name] = -diff if diff > 0 else abs(diff)
            else:
                # Для остальных больше = лучше
                diff = val_b - val_a
                improvements[name] = diff

        # Определение победителя
        if evaluation_b.score > evaluation_a.score:
            winner = 'B'
        elif evaluation_a.score > evaluation_b.score:
            winner = 'A'
        else:
            winner = 'TIE'

        return winner, improvements

    def get_metrics_report(
        self,
        evaluation: EvaluationResult
    ) -> Dict[str, Any]:
        """
        Получение отчёта по метрикам.

        ARGS:
        - evaluation: результат оценки

        RETURNS:
        - Dict[str, Any]: отчёт
        """
        return {
            'version_id': evaluation.version_id,
            'metrics': {
                'success_rate': evaluation.success_rate,
                'execution_success': evaluation.execution_success,
                'sql_validity': evaluation.sql_validity,
                'latency_ms': evaluation.latency,
                'error_rate': evaluation.error_rate
            },
            'score': evaluation.score,
            'meets_min_success_rate': evaluation.success_rate >= self.config.min_success_rate,
            'meets_max_latency': evaluation.latency <= self.config.max_latency_ms,
            'score_breakdown': {
                'success_rate_contribution': evaluation.success_rate * self.config.success_rate_weight,
                'execution_success_contribution': evaluation.execution_success * self.config.execution_success_weight,
                'sql_validity_contribution': evaluation.sql_validity * self.config.sql_validity_weight,
                'latency_penalty': min(evaluation.latency / 1000, 1.0) * self.config.latency_weight
            }
        }

    def calculate_correlation(
        self,
        evaluations: List[EvaluationResult]
    ) -> Dict[str, float]:
        """
        Расчёт корреляции score с success_rate.

        Цель: корреляция > 0.8

        ARGS:
        - evaluations: список оценок

        RETURNS:
        - Dict[str, float]: корреляции
        """
        if len(evaluations) < 2:
            return {'score_success_correlation': 0.0}

        scores = [e.score for e in evaluations]
        success_rates = [e.success_rate for e in evaluations]

        # Простой расчёт корреляции Пирсона
        n = len(evaluations)
        mean_scores = sum(scores) / n
        mean_success = sum(success_rates) / n

        numerator = sum(
            (s - mean_scores) * (r - mean_success)
            for s, r in zip(scores, success_rates)
        )

        denom_scores = sum((s - mean_scores) ** 2 for s in scores) ** 0.5
        denom_success = sum((r - mean_success) ** 2 for r in success_rates) ** 0.5

        if denom_scores == 0 or denom_success == 0:
            return {'score_success_correlation': 0.0}

        correlation = numerator / (denom_scores * denom_success)

        return {
            'score_success_correlation': correlation,
            'meets_threshold': abs(correlation) > 0.8
        }


# Import for async logging
import asyncio
