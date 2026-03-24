"""
Сервис оптимизации (Optimization Service).

КОМПОНЕНТЫ:
- OptimizationService: оркестрация цикла оптимизации

FEATURES:
- Автоматический запуск цикла оптимизации
- Анализ неудач для понимания проблем
- Генерация новых версий промптов
- Проверка необходимости оптимизации
- Блокировка для предотвращения параллельных циклов
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from core.models.data.benchmark import (
    FailureAnalysis,
    OptimizationMode,
    OptimizationResult,
    TargetMetric,
)
from core.application.services.benchmark_service import BenchmarkService
from core.application.services.prompt_contract_generator import PromptContractGenerator
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging import EventBusLogger
from core.application.services.metrics_publisher import MetricsPublisher


@dataclass
class OptimizationConfig:
    """Конфигурация оптимизации"""
    max_iterations: int = 5
    target_accuracy: float = 0.9
    min_improvement: float = 0.05  # 5% минимальное улучшение
    timeout_seconds: int = 300
    max_concurrent: int = 1  # Максимум параллельных оптимизаций


@dataclass
class OptimizationLock:
    """Блокировка для предотвращения параллельных оптимизаций"""
    capability: str
    acquired_at: datetime
    expires_at: datetime
    owner: str = "default"


class OptimizationService:
    """
    Сервис оптимизации промптов и контрактов.

    RESPONSIBILITIES:
    - Запуск цикла оптимизации
    - Анализ неудач
    - Генерация новых версий
    - Проверка необходимости оптимизации
    - Управление блокировками

    USAGE:
    ```python
    service = OptimizationService(benchmark_service, generator, metrics_collector, log_collector, event_bus)
    result = await service.start_optimization_cycle('capability', mode=OptimizationMode.ACCURACY)
    ```
    """

    def __init__(
        self,
        benchmark_service: BenchmarkService,
        prompt_generator: PromptContractGenerator,
        metrics_collector: MetricsCollector,
        event_bus: UnifiedEventBus,
        metrics_publisher: Optional[MetricsPublisher] = None,
        config: Optional[OptimizationConfig] = None
    ):
        """
        Инициализация сервиса оптимизации.

        ARGS:
        - benchmark_service: сервис бенчмарков
        - prompt_generator: генератор промптов
        - metrics_collector: сборщик метрик (для получения агрегированных метрик)
        - event_bus: шина событий
        - metrics_publisher: публикатор метрик (опционально, создаётся автоматически)
        - config: конфигурация оптимизации
        """
        self.benchmark_service = benchmark_service
        self.prompt_generator = prompt_generator
        self.metrics_collector = metrics_collector
        self.event_bus = event_bus
        self.config = config or OptimizationConfig()
        self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="OptimizationService")
        
        # Session handler устанавливается отдельно (after construction)
        self.session_handler = None

        # Используем MetricsPublisher если предоставлен
        # Если metrics_collector=None (тесты), то metrics_publisher тоже None
        self.metrics_publisher = None
        if metrics_publisher:
            self.metrics_publisher = metrics_publisher
        elif metrics_collector and hasattr(metrics_collector, 'storage') and metrics_collector.storage:
            # Создаём MetricsPublisher из существующих компонентов для обратной совместимости
            # НОВЫЙ API: MetricsPublisher
            self.metrics_publisher = MetricsPublisher(
                storage=metrics_collector.storage,
                event_bus=event_bus
            )

        # Активные блокировки
        self._locks: Dict[str, OptimizationLock] = {}
        self._lock = asyncio.Lock()

    async def start_optimization_cycle(
        self,
        capability: str,
        mode: OptimizationMode = OptimizationMode.ACCURACY,
        target_metrics: Optional[List[TargetMetric]] = None
    ) -> Optional[OptimizationResult]:
        """
        Запуск цикла оптимизации.

        ARGS:
        - capability: название способности для оптимизации
        - mode: режим оптимизации
        - target_metrics: целевые метрики

        RETURNS:
        - OptimizationResult: результат оптимизации или None если не удалось начать
        """
        await self.event_bus_logger.info(f"Запуск оптимизации для {capability} (режим: {mode.value})")

        # Публикация метрики начала оптимизации
        # НОВЫЙ API: MetricsPublisher
        await self.metrics_publisher.counter(
            name="optimization_cycle_started",
            capability=capability,
            tags={"mode": mode.value}
        )

        # СТАРЫЙ API (закомментирован для обратной совместимости):
        # await self.metrics_collector.storage.record(MetricRecord(
        #     agent_id="system",
        #     capability=capability,
        #     metric_type=MetricType.COUNTER,
        #     name="optimization_cycle_started",
        #     value=1.0,
        #     tags={"mode": mode.value}
        # ))

        # Проверка возможности оптимизации
        if not await self._is_capability_optimizable(capability):
            await self.event_bus_logger.warning(f"Capability {capability} не может быть оптимизирован")
            return None

        # Проверка необходимости оптимизации
        if not await self._needs_optimization(capability, mode):
            await self.event_bus_logger.info(f"Оптимизация не требуется для {capability}")
            return None

        # Попытка acquire lock
        if not await self._acquire_lock(capability):
            await self.event_bus_logger.warning(f"Оптимизация уже выполняется для {capability}")
            return None

        try:
            # Публикация события начала
            await self._publish_optimization_start(capability, mode)

            # Получение текущей версии
            current_version = await self._get_current_version(capability)

            # Анализ неудач
            failure_analysis = await self._analyze_failures(capability, current_version)

            # Инициализация результата
            result = OptimizationResult(
                capability=capability,
                from_version=current_version,
                to_version=current_version,
                mode=mode,
                iterations=0,
                failure_analysis=failure_analysis
            )

            # Цикл оптимизации
            for iteration in range(self.config.max_iterations):
                result.iterations = iteration + 1

                # Публикация метрики итерации
                # НОВЫЙ API: MetricsPublisher
                await self.metrics_publisher.gauge(
                    name="optimization_iteration",
                    value=iteration + 1,
                    capability=capability,
                    tags={"mode": mode.value}
                )

                # СТАРЫЙ API (закомментирован для обратной совместимости):
                # await self.metrics_collector.storage.record(MetricRecord(
                #     agent_id="system",
                #     capability=capability,
                #     metric_type=MetricType.GAUGE,
                #     name="optimization_iteration",
                #     value=iteration + 1,
                #     tags={"mode": mode.value}
                # ))

                # Генерация новой версии
                new_prompt, new_contract = await self.prompt_generator.generate_and_save(
                    original_prompt=await self._get_current_prompt(capability, current_version),
                    failure_analysis=failure_analysis,
                    target_improvement=self._get_target_improvement(mode, target_metrics)
                )

                if not new_prompt:
                    await self.event_bus_logger.error("Не удалось сгенерировать новую версию")
                    break

                new_version = new_prompt.version

                # Тестирование новой версии
                test_result = await self._test_new_version(capability, new_version, current_version)

                # Обновление метрик
                result.final_metrics = test_result.get('metrics', {})

                # Проверка улучшения
                if self._is_improvement(result.initial_metrics, result.final_metrics, mode):
                    result.to_version = new_version

                    # Публикация метрики успешной оптимизации
                    # НОВЫЙ API: MetricsPublisher
                    await self.metrics_publisher.counter(
                        name="optimization_success",
                        capability=capability,
                        tags={"mode": mode.value, "version": new_version}
                    )

                    # СТАРЫЙ API (закомментирован для обратной совместимости):
                    # await self.metrics_collector.storage.record(MetricRecord(
                    #     agent_id="system",
                    #     capability=capability,
                    #     metric_type=MetricType.COUNTER,
                    #     name="optimization_success",
                    #     value=1.0,
                    #     tags={"mode": mode.value, "version": new_version}
                    # ))

                    # Проверка достижения цели
                    if self._is_target_achieved(result.final_metrics, target_metrics):
                        result.target_achieved = True

                        # Публикация метрики достижения цели
                        # НОВЫЙ API: MetricsPublisher
                        await self.metrics_publisher.gauge(
                            name="optimization_target_achieved",
                            value=1.0,
                            capability=capability,
                            tags={"mode": mode.value, "version": new_version}
                        )

                        # СТАРЫЙ API (закомментирован для обратной совместимости):
                        # await self.metrics_collector.storage.record(MetricRecord(
                        #     agent_id="system",
                        #     capability=capability,
                        #     metric_type=MetricType.GAUGE,
                        #     name="optimization_target_achieved",
                        #     value=1.0,
                        #     tags={"mode": mode.value, "version": new_version}
                        # ))

                        # Продвижение версии
                        await self.benchmark_service.promote_version(
                            capability,
                            current_version,
                            new_version,
                            reason=f"Optimization {mode.value} achieved"
                        )

                        break
                else:
                    await self.event_bus_logger.info(f"Версия {new_version} не показала улучшения")
                    # Публикация метрики неудачной оптимизации
                    # НОВЫЙ API: MetricsPublisher
                    await self.metrics_publisher.counter(
                        name="optimization_failure",
                        capability=capability,
                        tags={"mode": mode.value, "version": new_version}
                    )

                    # СТАРЫЙ API (закомментирован для обратной совместимости):
                    # await self.metrics_collector.storage.record(MetricRecord(
                    #     agent_id="system",
                    #     capability=capability,
                    #     metric_type=MetricType.COUNTER,
                    #     name="optimization_failure",
                    #     value=1.0,
                    #     tags={"mode": mode.value, "version": new_version}
                    # ))

                    # Отклонение версии
                    await self.benchmark_service.reject_version(
                        capability,
                        new_version,
                        reason="No improvement"
                    )

            # Расчёт улучшений
            result.calculate_improvements()

            # Публикация метрики завершения оптимизации
            # НОВЫЙ API: MetricsPublisher
            await self.metrics_publisher.gauge(
                name="optimization_improvement",
                value=result.improvements.get('accuracy', 0),
                capability=capability,
                tags={"mode": mode.value, "iterations": str(result.iterations)}
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.metrics_collector.storage.record(MetricRecord(
            #     agent_id="system",
            #     capability=capability,
            #     metric_type=MetricType.GAUGE,
            #     name="optimization_improvement",
            #     value=result.improvements.get('accuracy', 0),
            #     tags={"mode": mode.value, "iterations": str(result.iterations)}
            # ))

            # Публикация события завершения
            await self._publish_optimization_complete(result)

            await self.event_bus_logger.info(f"Оптимизация завершена: {result.from_version} → {result.to_version}")

            return result

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка оптимизации: {e}")
            # Публикация метрики ошибки оптимизации
            # НОВЫЙ API: MetricsPublisher
            await self.metrics_publisher.counter(
                name="optimization_error",
                capability=capability,
                tags={"mode": mode.value, "error_type": type(e).__name__}
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.metrics_collector.storage.record(MetricRecord(
            #     agent_id="system",
            #     capability=capability,
            #     metric_type=MetricType.COUNTER,
            #     name="optimization_error",
            #     value=1.0,
            #     tags={"mode": mode.value, "error_type": type(e).__name__}
            # ))

            return None

        finally:
            # Release lock
            await self._release_lock(capability)

    async def _analyze_failures(self, capability: str, version: str) -> FailureAnalysis:
        """
        Анализ неудач для capability.

        ARGS:
        - capability: название способности
        - version: версия для анализа

        RETURNS:
        - FailureAnalysis: анализ неудач
        """
        await self.event_bus_logger.info(f"Анализ неудач для {capability}@{version}")

        # Получение логов ошибок из session_handler
        error_logs = []
        if self.session_handler:
            error_logs = await self.session_handler.get_error_logs(
                capability=capability,
                limit=100
            )

        # Публикация метрики анализа неудач
        # НОВЫЙ API: MetricsPublisher
        await self.metrics_publisher.gauge(
            name="failure_analysis_total_failures",
            value=len(error_logs),
            capability=capability,
            tags={"version": version}
        )

        # Создание анализа
        analysis = FailureAnalysis(
            capability=capability,
            version=version,
            total_failures=len(error_logs)
        )

        # Группировка по типам ошибок
        error_types: Dict[str, int] = {}
        for log in error_logs:
            # log — это dict, не LogEntry
            error_type = log.get('error_type', log.get('error_message', 'unknown'))[:50]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        # Публикация метрик по типам ошибок
        # НОВЫЙ API: MetricsPublisher
        for error_type, count in error_types.items():
            await self.metrics_publisher.gauge(
                name="failure_analysis_error_type",
                value=count,
                capability=capability,
                tags={"version": version, "error_type": error_type}
            )

            # СТАРЫЙ API (закомментирован для обратной совместимости):
            # await self.metrics_collector.storage.record(MetricRecord(
            #     agent_id="system",
            #     capability=capability,
            #     metric_type=MetricType.GAUGE,
            #     name="failure_analysis_error_type",
            #     value=count,
            #     tags={"version": version, "error_type": error_type}
            # ))

        # Добавление категорий
        for error_type, count in error_types.items():
            analysis.add_failure_category(error_type, count)

        # Генерация рекомендаций на основе анализа
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _generate_recommendations(self, analysis: FailureAnalysis) -> List[str]:
        """
        Генерация рекомендаций на основе анализа.

        ARGS:
        - analysis: анализ неудач

        RETURNS:
        - List[str]: список рекомендаций
        """
        recommendations = []

        top_categories = analysis.get_top_failure_categories(3)

        for category, count in top_categories:
            if 'syntax' in category.lower():
                recommendations.append("Improve input validation and syntax checking")
            elif 'timeout' in category.lower():
                recommendations.append("Add timeout handling and retry logic")
            elif 'validation' in category.lower():
                recommendations.append("Enhance schema validation")
            elif 'logic' in category.lower():
                recommendations.append("Clarify decision logic in prompt")
            else:
                recommendations.append(f"Address {category} errors")

        return recommendations

    async def _needs_optimization(self, capability: str, mode: OptimizationMode) -> bool:
        """
        Проверка необходимости оптимизации.

        ARGS:
        - capability: название способности
        - mode: режим оптимизации

        RETURNS:
        - bool: требуется ли оптимизация
        """
        # Получение текущих метрик
        # ИСПОЛЬЗУЕМ старый API через metrics_collector (агрегация остаётся там)
        metrics = await self.metrics_collector.get_aggregated_metrics(
            capability,
            version='latest'
        )

        # Публикация метрик для мониторинга
        # НОВЫЙ API: MetricsPublisher
        await self.metrics_publisher.gauge(
            name="optimization_check_accuracy",
            value=metrics.accuracy,
            capability=capability,
            tags={"mode": mode.value}
        )

        # СТАРЫЙ API (закомментирован для обратной совместимости):
        # await self.metrics_collector.storage.record(MetricRecord(
        #     agent_id="system",
        #     capability=capability,
        #     metric_type=MetricType.GAUGE,
        #     name="optimization_check_accuracy",
        #     value=metrics.accuracy,
        #     tags={"mode": mode.value}
        # ))

        if mode == OptimizationMode.ACCURACY:
            return metrics.accuracy < self.config.target_accuracy
        elif mode == OptimizationMode.SPEED:
            return metrics.avg_execution_time_ms > 500  # Пример порога
        elif mode == OptimizationMode.TOKENS:
            return metrics.avg_tokens > 1000  # Пример порога
        else:
            return metrics.accuracy < self.config.target_accuracy

    async def _is_capability_optimizable(self, capability: str) -> bool:
        """
        Проверка возможности оптимизации capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - bool: может ли быть оптимизирован
        """
        # Проверка что capability существует
        # Проверка что есть метрики для анализа
        # Проверка что не в чёрном списке

        # TODO: Реализовать проверку
        return True

    async def _acquire_lock(self, capability: str) -> bool:
        """
        Acquire lock для оптимизации.

        ARGS:
        - capability: название способности

        RETURNS:
        - bool: успешно ли acquired
        """
        async with self._lock:
            if capability in self._locks:
                lock = self._locks[capability]
                if lock.expires_at > datetime.now():
                    return False  # Lock ещё активен

            # Создание нового lock
            self._locks[capability] = OptimizationLock(
                capability=capability,
                acquired_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=self.config.timeout_seconds)
            )

            return True

    async def _release_lock(self, capability: str) -> None:
        """
        Release lock.

        ARGS:
        - capability: название способности
        """
        async with self._lock:
            if capability in self._locks:
                del self._locks[capability]

    async def _get_current_version(self, capability: str) -> str:
        """Получение текущей версии"""
        # TODO: Получить из registry
        return "v1.0.0"

    async def _get_current_prompt(self, capability: str, version: str):
        """Получение текущего промпта"""
        # TODO: Загрузить из хранилища
        from core.models.data.prompt import Prompt
        from core.models.enums.common_enums import ComponentType

        return Prompt(
            capability=capability,
            version=version,
            content="Current prompt content",
            status='active',
            component_type=ComponentType.SKILL
        )

    def _get_target_improvement(self, mode: OptimizationMode, target_metrics: Optional[List[TargetMetric]]) -> str:
        """Получение целевого улучшения"""
        if target_metrics:
            return ", ".join([f"{m.name}: {m.target_value}" for m in target_metrics])
        return f"Improve {mode.value}"

    async def _test_new_version(self, capability: str, new_version: str, old_version: str) -> Dict[str, Any]:
        """
        Тестирование новой версии.

        ARGS:
        - capability: название способности
        - new_version: новая версия
        - old_version: старая версия

        RETURNS:
        - Dict: результаты тестов
        """
        # TODO: Запустить бенчмарки для сравнения
        return {
            'metrics': {
                'accuracy': 0.85,
                'avg_execution_time_ms': 150.0
            }
        }

    def _is_improvement(
        self,
        old_metrics: Dict[str, float],
        new_metrics: Dict[str, float],
        mode: OptimizationMode
    ) -> bool:
        """
        Проверка улучшения.

        ARGS:
        - old_metrics: старые метрики
        - new_metrics: новые метрики
        - mode: режим оптимизации

        RETURNS:
        - bool: есть ли улучшение
        """
        if mode == OptimizationMode.ACCURACY:
            old_acc = old_metrics.get('accuracy', 0)
            new_acc = new_metrics.get('accuracy', 0)
            return (new_acc - old_acc) >= self.config.min_improvement
        elif mode == OptimizationMode.SPEED:
            old_time = old_metrics.get('avg_execution_time_ms', float('inf'))
            new_time = new_metrics.get('avg_execution_time_ms', float('inf'))
            return new_time < old_time * (1 - self.config.min_improvement)
        else:
            return False

    def _is_target_achieved(
        self,
        metrics: Dict[str, float],
        target_metrics: Optional[List[TargetMetric]]
    ) -> bool:
        """
        Проверка достижения цели.

        ARGS:
        - metrics: текущие метрики
        - target_metrics: целевые метрики

        RETURNS:
        - bool: достигнута ли цель
        """
        if not target_metrics:
            return metrics.get('accuracy', 0) >= self.config.target_accuracy

        for target in target_metrics:
            current = metrics.get(target.name, 0)
            # Для speed/time меньше = лучше
            if target.name in ['speed', 'time', 'execution_time', 'avg_execution_time_ms']:
                if current > target.target_value:
                    return False
            else:
                # Для accuracy/score больше = лучше
                if current < target.target_value:
                    return False

        return True

    async def _publish_optimization_start(self, capability: str, mode: OptimizationMode) -> None:
        """Публикация события начала оптимизации"""
        await self.event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_STARTED,
            data={
                'capability': capability,
                'mode': mode.value,
                'target_accuracy': self.config.target_accuracy,
                'timestamp': datetime.now().isoformat()
            }
        )

    async def _publish_optimization_complete(self, result: OptimizationResult) -> None:
        """Публикация события завершения оптимизации"""
        await self.event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,
            data={
                'capability': result.capability,
                'from_version': result.from_version,
                'to_version': result.to_version,
                'iterations': result.iterations,
                'improvements': result.improvements,
                'target_achieved': result.target_achieved,
                'timestamp': result.timestamp.isoformat()
            }
        )

    async def get_optimization_status(self, capability: str) -> Dict[str, Any]:
        """
        Получение статуса оптимизации.

        ARGS:
        - capability: название способности

        RETURNS:
        - Dict: статус оптимизации
        """
        async with self._lock:
            if capability in self._locks:
                lock = self._locks[capability]
                return {
                    'status': 'running',
                    'acquired_at': lock.acquired_at.isoformat(),
                    'expires_at': lock.expires_at.isoformat()
                }
            else:
                return {'status': 'idle'}

    async def cancel_optimization(self, capability: str) -> bool:
        """
        Отмена оптимизации.

        ARGS:
        - capability: название способности

        RETURNS:
        - bool: успешно ли отменено
        """
        async with self._lock:
            if capability in self._locks:
                del self._locks[capability]
                await self.event_bus_logger.info(f"Оптимизация отменена для {capability}")
                return True
            return False
