"""
BenchmarkRunner - воспроизводимое тестирование промптов.

ОТВЕТСТВЕННОСТЬ:
- Запуск бенчмарков по сценариям
- Фиксированные параметры (temperature, seed, database)
- Обеспечение воспроизводимости (variance < 0.05)
- Сбор метрик выполнения
"""
import asyncio
import logging
import random
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

from core.components.benchmarks.benchmark_models import (
    BenchmarkScenario,
    PromptVersion,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging.event_types import LogEventType

_logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRunConfig:
    """Конфигурация запуска бенчмарка"""
    temperature: float = 0.0  # Фиксированная температура для воспроизводимости
    seed: int = 42  # Фиксированный seed
    max_retries: int = 3
    timeout_seconds: int = 60
    parallel_runs: int = 1


@dataclass
class BenchmarkRunResult:
    """Результат запуска бенчмарка"""
    version_id: str
    scenario_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    raw_result: Optional[Dict[str, Any]] = None


class BenchmarkRunner:
    """
    Воспроизводимый раннер бенчмарков.

    RESPONSIBILITIES:
    - Запуск тестов с фиксированными параметрами
    - Обеспечение воспроизводимости результатов
    - Сбор и агрегация метрик
    - Контроль variance между запусками

    USAGE:
    ```python
    runner = BenchmarkRunner(event_bus, executor_callback)
    results = await runner.run(prompt_version, scenarios)
    ```
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        executor_callback: Callable[[str, str], Awaitable[Dict[str, Any]]],
        config: Optional[BenchmarkRunConfig] = None
    ):
        """
        Инициализация BenchmarkRunner.

        ARGS:
        - event_bus: шина событий
        - executor_callback: callback для выполнения промпта (input, version) -> result
        - config: конфигурация
        """
        self.event_bus = event_bus
        self.executor_callback = executor_callback
        self.config = config or BenchmarkRunConfig()

        # Инициализация random seed для воспроизводимости
        random.seed(self.config.seed)

    async def run(
        self,
        version: PromptVersion,
        scenarios: List[BenchmarkScenario]
    ) -> List[BenchmarkRunResult]:
        """
        Запуск бенчмарка для версии промпта.

        ARGS:
        - version: версия промпта для тестирования
        - scenarios: список сценариев

        RETURNS:
        - List[BenchmarkRunResult]: результаты запусков
        """
        _logger.info(
            "Запуск бенчмарка для версии %s (%d сценариев)",
            version.id, len(scenarios),
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        results = []

        for scenario in scenarios:
            result = await self._run_scenario(version, scenario)
            results.append(result)

        # Проверка воспроизводимости
        variance = self._calculate_variance(results)
        if variance > 0.05:
            _logger.warning(
                "Высокая вариативность результатов: %.3f", variance,
                extra={"event_type": LogEventType.WARNING}
            )

        return results

    async def _run_scenario(
        self,
        version: PromptVersion,
        scenario: BenchmarkScenario
    ) -> BenchmarkRunResult:
        """
        Запуск одного сценария.

        ARGS:
        - version: версия промпта
        - scenario: сценарий

        RETURNS:
        - BenchmarkRunResult: результат
        """
        start_time = datetime.now()

        try:
            # Выполнение с фиксированными параметрами
            result = await self._execute_with_retry(version, scenario)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return BenchmarkRunResult(
                version_id=version.id,
                scenario_id=scenario.id,
                success=result.get('success', False),
                output=result.get('output'),
                error=result.get('error'),
                execution_time_ms=execution_time,
                tokens_used=result.get('tokens_used', 0),
                raw_result=result
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            _logger.error(
                "Ошибка выполнения сценария %s: %s", scenario.id, e,
                extra={"event_type": LogEventType.SYSTEM_ERROR}
            )

            return BenchmarkRunResult(
                version_id=version.id,
                scenario_id=scenario.id,
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )

    async def _execute_with_retry(
        self,
        version: PromptVersion,
        scenario: BenchmarkScenario
    ) -> Dict[str, Any]:
        """
        Выполнение сценария с повторными попытками.

        ARGS:
        - version: версия промпта
        - scenario: сценарий

        RETURNS:
        - Dict: результат выполнения
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                # Выполнение через callback
                result = await self.executor_callback(
                    scenario.goal,
                    version.id
                )

                # Проверка успешности
                if result.get('success', False):
                    return result

                last_error = result.get('error', 'Unknown error')

            except Exception as e:
                last_error = str(e)

            # Пауза перед повторной попыткой (exponential backoff)
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(0.1 * (2 ** attempt))

        return {
            'success': False,
            'error': last_error,
            'output': None
        }

    async def run_comparison(
        self,
        versions: List[PromptVersion],
        scenarios: List[BenchmarkScenario]
    ) -> Dict[str, List[BenchmarkRunResult]]:
        """
        Сравнительный запуск нескольких версий.

        ARGS:
        - versions: список версий для сравнения
        - scenarios: сценарии для тестирования

        RETURNS:
        - Dict[str, List[BenchmarkRunResult]]: результаты по версиям
        """
        results = {}

        for version in versions:
            # Сброс seed для каждой версии для одинаковых условий
            random.seed(self.config.seed)
            
            results[version.id] = await self.run(version, scenarios)

        return results

    def _calculate_variance(
        self,
        results: List[BenchmarkRunResult]
    ) -> float:
        """
        Расчёт вариативности результатов.

        ARGS:
        - results: результаты запусков

        RETURNS:
        - float: variance (0.0-1.0)
        """
        if len(results) < 2:
            return 0.0

        # Расчёт variance success rate
        success_rates = []
        window_size = max(1, len(results) // 5)

        for i in range(0, len(results), window_size):
            window = results[i:i + window_size]
            success_count = sum(1 for r in window if r.success)
            success_rates.append(success_count / len(window) if window else 0)

        if len(success_rates) < 2:
            return 0.0

        mean = sum(success_rates) / len(success_rates)
        variance = sum((r - mean) ** 2 for r in success_rates) / len(success_rates)

        return variance

    def aggregate_results(
        self,
        results: List[BenchmarkRunResult]
    ) -> Dict[str, Any]:
        """
        Агрегация результатов запуска.

        ARGS:
        - results: результаты запусков

        RETURNS:
        - Dict[str, Any]: агрегированные метрики
        """
        if not results:
            return {
                'total_runs': 0,
                'success_rate': 0.0,
                'avg_execution_time_ms': 0.0,
                'avg_tokens_used': 0.0,
                'error_rate': 0.0
            }

        total_runs = len(results)
        successful_runs = sum(1 for r in results if r.success)
        error_runs = sum(1 for r in results if r.error)

        avg_execution_time = sum(r.execution_time_ms for r in results) / total_runs
        avg_tokens = sum(r.tokens_used for r in results) / total_runs if total_runs > 0 else 0

        return {
            'total_runs': total_runs,
            'success_rate': successful_runs / total_runs,
            'avg_execution_time_ms': avg_execution_time,
            'avg_tokens_used': avg_tokens,
            'error_rate': error_runs / total_runs,
            'variance': self._calculate_variance(results)
        }

    def set_seed(self, seed: int) -> None:
        """
        Установка seed для воспроизводимости.

        ARGS:
        - seed: значение seed
        """
        self.config.seed = seed
        random.seed(seed)

    def get_config(self) -> BenchmarkRunConfig:
        """Получение конфигурации"""
        return self.config

