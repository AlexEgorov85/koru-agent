"""
ABTester — A/B тестирование версий промптов.

ОТВЕТСТВЕННОСТЬ:
- Запуск старого и нового промпта на одних данных
- Сбор и сравнение метрик
- Safety check (не стало ли хуже)
"""
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass
import asyncio

from core.models.data.prompt import Prompt
from core.models.data.execution_trace import ExecutionTrace


@dataclass
class ABTestResult:
    """Результат A/B теста"""
    # Метрики версии A (старая)
    metrics_a: Dict[str, float]
    
    # Метрики версии B (новая)
    metrics_b: Dict[str, float]
    
    # Улучшения
    improvements: Dict[str, float]  # % улучшения
    
    # Победитель
    winner: str  # 'A', 'B', or 'TIE'
    
    # Статистическая значимость
    statistically_significant: bool
    
    # Детали
    details: str


@dataclass
class ABTestConfig:
    """Конфигурация A/B теста"""
    # Минимальное улучшение для победы
    min_improvement: float = 0.05  # 5%
    
    # Максимально допустимое ухудшение
    max_regression: float = 0.02  # 2%
    
    # Количество запусков для статистики
    num_runs: int = 3
    
    # Таймаут на запуск
    timeout_seconds: int = 60


class ABTester:
    """
    A/B тестирование версий промптов.

    USAGE:
    ```python
    tester = ABTester(executor_callback)
    
    result = await tester.run_test(
        prompt_a=old_prompt,
        prompt_b=new_prompt,
        test_data=test_cases
    )
    
    if result.winner == 'B':
    ```
    """

    def __init__(
        self,
        executor_callback: Callable[[str, str], Awaitable[Dict[str, Any]]],
        config: Optional[ABTestConfig] = None
    ):
        """
        Инициализация.

        ARGS:
        - executor_callback: функция для выполнения промпта (input, version_id) -> result
        - config: конфигурация
        """
        self.executor_callback = executor_callback
        self.config = config or ABTestConfig()

    async def run_test(
        self,
        prompt_a: Prompt,
        prompt_b: Prompt,
        test_data: List[Dict[str, Any]]
    ) -> ABTestResult:
        """
        Запуск A/B теста.

        ARGS:
        - prompt_a: старая версия
        - prompt_b: новая версия
        - test_data: тестовые данные

        RETURNS:
        - ABTestResult: результат теста
        """
        # Запуск тестов для обеих версий
        results_a = await self._run_version(prompt_a, test_data)
        results_b = await self._run_version(prompt_b, test_data)

        # Агрегация метрик
        metrics_a = self._aggregate_metrics(results_a)
        metrics_b = self._aggregate_metrics(results_b)

        # Расчёт улучшений
        improvements = self._calculate_improvements(metrics_a, metrics_b)

        # Определение победителя
        winner = self._determine_winner(metrics_a, metrics_b, improvements)

        # Проверка статистической значимости
        significant = self._check_significance(results_a, results_b)

        # Детали
        details = self._generate_details(metrics_a, metrics_b, improvements)

        return ABTestResult(
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            improvements=improvements,
            winner=winner,
            statistically_significant=significant,
            details=details
        )

    async def _run_version(
        self,
        prompt: Prompt,
        test_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Запуск версии на тестовых данных.

        ARGS:
        - prompt: промпт для тестирования
        - test_data: тестовые данные

        RETURNS:
        - List[Dict]: результаты запусков
        """
        results = []

        for i, test_case in enumerate(test_data[:self.config.num_runs]):
            try:
                # Запуск с таймаутом
                result = await asyncio.wait_for(
                    self.executor_callback(test_case.get('input', ''), prompt.version),
                    timeout=self.config.timeout_seconds
                )
                results.append(result)
            except asyncio.TimeoutError:
                results.append({
                    'success': False,
                    'error': 'timeout',
                    'execution_time_ms': self.config.timeout_seconds * 1000
                })
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e),
                    'execution_time_ms': 0
                })

        return results

    def _aggregate_metrics(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Агрегация метрик из результатов.

        ARGS:
        - results: результаты запусков

        RETURNS:
        - Dict[str, float]: агрегированные метрики
        """
        if not results:
            return {
                'success_rate': 0.0,
                'avg_execution_time_ms': 0.0,
                'avg_tokens': 0.0
            }

        total = len(results)
        successful = sum(1 for r in results if r.get('success', False))

        success_rate = successful / total

        avg_time = sum(
            r.get('execution_time_ms', 0) for r in results
        ) / total

        avg_tokens = sum(
            r.get('tokens_used', 0) for r in results
        ) / total

        return {
            'success_rate': success_rate,
            'avg_execution_time_ms': avg_time,
            'avg_tokens': avg_tokens
        }

    def _calculate_improvements(
        self,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Расчёт улучшений в процентах.

        ARGS:
        - metrics_a: метрики версии A
        - metrics_b: метрики версии B

        RETURNS:
        - Dict[str, float]: улучшения в %
        """
        improvements = {}

        # success_rate: больше = лучше
        if metrics_a.get('success_rate', 0) > 0:
            improvements['success_rate'] = (
                (metrics_b['success_rate'] - metrics_a['success_rate']) /
                metrics_a['success_rate']
            ) * 100
        else:
            improvements['success_rate'] = 100.0 if metrics_b.get('success_rate', 0) > 0 else 0.0

        # execution_time: меньше = лучше
        if metrics_a.get('avg_execution_time_ms', 0) > 0:
            improvements['execution_time'] = (
                (metrics_a['avg_execution_time_ms'] - metrics_b['avg_execution_time_ms']) /
                metrics_a['avg_execution_time_ms']
            ) * 100
        else:
            improvements['execution_time'] = 0.0

        # tokens: меньше = лучше
        if metrics_a.get('avg_tokens', 0) > 0:
            improvements['tokens'] = (
                (metrics_a['avg_tokens'] - metrics_b['avg_tokens']) /
                metrics_a['avg_tokens']
            ) * 100
        else:
            improvements['tokens'] = 0.0

        return improvements

    def _determine_winner(
        self,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float],
        improvements: Dict[str, float]
    ) -> str:
        """
        Определение победителя.

        ARGS:
        - metrics_a: метрики версии A
        - metrics_b: метрики версии B
        - improvements: улучшения

        RETURNS:
        - str: 'A', 'B', or 'TIE'
        """
        # Проверка на регрессию
        if improvements.get('success_rate', 0) < -self.config.max_regression * 100:
            return 'A'  # Новая версия хуже

        # Проверка на улучшение
        if improvements.get('success_rate', 0) >= self.config.min_improvement * 100:
            return 'B'  # Новая версия лучше

        # Проверка на улучшение по времени
        if improvements.get('execution_time', 0) >= self.config.min_improvement * 100:
            return 'B'

        # Ничья
        return 'TIE'

    def _check_significance(
        self,
        results_a: List[Dict[str, Any]],
        results_b: List[Dict[str, Any]]
    ) -> bool:
        """
        Проверка статистической значимости.

        Упрощённая проверка: достаточно ли данных

        ARGS:
        - results_a: результаты версии A
        - results_b: результаты версии B

        RETURNS:
        - bool: значимо ли
        """
        # Нужно минимум 3 запуска для статистики
        return len(results_a) >= 3 and len(results_b) >= 3

    def _generate_details(
        self,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float],
        improvements: Dict[str, float]
    ) -> str:
        """
        Генерация деталей теста.

        ARGS:
        - metrics_a: метрики версии A
        - metrics_b: метрики версии B
        - improvements: улучшения

        RETURNS:
        - str: детали
        """
        lines = [
            f"Success Rate: {metrics_a.get('success_rate', 0):.1%} → {metrics_b.get('success_rate', 0):.1%} ({improvements.get('success_rate', 0):+.1f}%)",
            f"Execution Time: {metrics_a.get('avg_execution_time_ms', 0):.0f}ms → {metrics_b.get('avg_execution_time_ms', 0):.0f}ms ({improvements.get('execution_time', 0):+.1f}%)",
            f"Tokens: {metrics_a.get('avg_tokens', 0):.0f} → {metrics_b.get('avg_tokens', 0):.0f} ({improvements.get('tokens', 0):+.1f}%)"
        ]

        return "\n".join(lines)
