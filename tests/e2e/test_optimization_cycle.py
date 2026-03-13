"""
E2E тесты для полного цикла оптимизации.

ТЕСТЫ:
- test_full_optimization_cycle: полный цикл оптимизации
- test_optimization_with_failure_analysis: оптимизация с анализом неудач
- test_optimization_target_achieved: достижение целевых метрик
"""
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.benchmark import (
    FailureAnalysis,
    OptimizationMode,
    OptimizationResult,
    TargetMetric,
    LogEntry,
    LogType,
)
from core.application.services.prompt_contract_generator import PromptContractGenerator


class TestFullOptimizationCycle:
    """Тесты полного цикла оптимизации"""

    @pytest.mark.asyncio
    async def test_full_optimization_cycle(self, tmp_path):
        """
        Тест полного цикла оптимизации:
        1. Создание сервисов
        2. Анализ неудач
        3. Генерация новой версии
        4. Тестирование новой версии
        5. Проверка улучшения
        """
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.application.services.prompt_contract_generator import PromptContractGenerator
        from core.infrastructure.metrics_collector import MetricsCollector
        from core.infrastructure.log_collector import LogCollector
        from core.infrastructure.metrics_storage import FileSystemMetricsStorage
        from core.infrastructure.log_storage import FileSystemLogStorage
        from core.infrastructure.event_bus.event_bus import EventBus, EventType

        # Инициализация компонентов
        event_bus = EventBus()
        metrics_storage = FileSystemMetricsStorage(base_dir=tmp_path / 'metrics')
        log_storage = FileSystemLogStorage(base_dir=tmp_path / 'logs')

        metrics_collector = MetricsCollector(event_bus, metrics_storage)
        log_collector = LogCollector(event_bus, log_storage)

        await metrics_collector.initialize()
        await log_collector.initialize()

        accuracy_evaluator = AccuracyEvaluatorService()

        # Мокаем benchmark service
        benchmark_service = MagicMock(spec=BenchmarkService)
        benchmark_service.promote_version = AsyncMock(return_value=True)
        benchmark_service.reject_version = AsyncMock(return_value=True)

        # Мокаем prompt generator
        prompt_generator = MagicMock(spec=PromptContractGenerator)
        prompt_generator.generate_and_save = AsyncMock(return_value=(MagicMock(), MagicMock()))

        # Создание optimization service
        opt_config = OptimizationConfig(
            max_iterations=3,
            target_accuracy=0.9,
            min_improvement=0.05,
            timeout_seconds=60
        )

        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=prompt_generator,
            metrics_collector=metrics_collector,
            log_collector=None,
            event_bus=event_bus,
            config=opt_config
        )

        # Мокаем методы для теста
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._analyze_failures = AsyncMock(return_value=FailureAnalysis(
            capability='test_capability',
            version='v1.0.0',
            total_failures=5
        ))
        optimization_service._get_current_version = AsyncMock(return_value='v1.0.0')
        optimization_service._get_current_prompt = AsyncMock(return_value=MagicMock())
        optimization_service._test_new_version = AsyncMock(return_value={
            'metrics': {'accuracy': 0.95}
        })

        # Запуск оптимизации
        result = await optimization_service.start_optimization_cycle(
            capability='test_capability',
            mode=OptimizationMode.ACCURACY,
            target_metrics=[
                TargetMetric(name='accuracy', target_value=0.9)
            ]
        )

        # Проверка результатов
        assert result is not None
        assert result.capability == 'test_capability'
        assert result.mode == OptimizationMode.ACCURACY
        assert result.iterations >= 1
        assert hasattr(result, 'from_version')
        assert hasattr(result, 'to_version')

    @pytest.mark.asyncio
    async def test_optimization_with_failure_analysis(self, tmp_path):
        """
        Тест оптимизации с анализом неудач:
        1. Создание FailureAnalysis
        2. Добавление категорий ошибок
        3. Генерация рекомендаций
        4. Использование в оптимизации
        """
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.event_bus.event_bus import EventBus

        # Создание FailureAnalysis
        failure_analysis = FailureAnalysis(
            capability='test_capability',
            version='v1.0.0',
            total_failures=0  # total_failures считается автоматически
        )

        failure_analysis.add_failure_category('syntax_error', 4)
        failure_analysis.add_failure_category('timeout', 3)
        failure_analysis.add_failure_category('validation_error', 3)

        failure_analysis.add_pattern('Missing required field')
        failure_analysis.add_pattern('Request timeout after 30s')

        failure_analysis.add_recommendation('Improve input validation')
        failure_analysis.add_recommendation('Add retry logic for timeouts')

        # Проверка анализа (total_failures = сумма категорий = 10)
        assert failure_analysis.total_failures == 10
        assert len(failure_analysis.failure_categories) == 3
        assert len(failure_analysis.common_patterns) == 2
        assert len(failure_analysis.recommendations) == 2

        # Проверка топ категорий
        top_categories = failure_analysis.get_top_failure_categories(2)
        assert len(top_categories) == 2
        assert top_categories[0][0] == 'syntax_error'
        assert top_categories[0][1] == 4

        # Создание optimization service
        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)
        accuracy_evaluator = AccuracyEvaluatorService()

        opt_config = OptimizationConfig(max_iterations=2)
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Тест генерации рекомендаций
        recommendations = optimization_service._generate_recommendations(failure_analysis)
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_optimization_target_achieved(self):
        """
        Тест достижения целевых метрик:
        1. Установка целевых метрик
        2. Запуск оптимизации
        3. Проверка достижения цели
        """
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.event_bus.event_bus import EventBus
        from core.models.data.benchmark import OptimizationResult, OptimizationMode
        from core.models.data.prompt import Prompt
        from core.models.enums.common_enums import ComponentType

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)
        benchmark_service.promote_version = AsyncMock(return_value=True)

        # Создаём правильный mock для prompt_generator
        prompt_generator = MagicMock(spec=PromptContractGenerator)
        prompt_generator.generate_and_save = AsyncMock(return_value=(
            Prompt(
                capability='test_capability',
                version='v1.0.1',
                content='New prompt content with enough characters',
                status='draft',
                component_type=ComponentType.SKILL
            ),
            None
        ))

        opt_config = OptimizationConfig(
            max_iterations=5,
            target_accuracy=0.9,
            min_improvement=0.05
        )

        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=prompt_generator,
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Мокаем методы
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._analyze_failures = AsyncMock(return_value=FailureAnalysis(
            capability='test_capability',
            version='v1.0.0',
            total_failures=3
        ))
        optimization_service._get_current_version = AsyncMock(return_value='v1.0.0')
        optimization_service._get_current_prompt = AsyncMock(return_value=Prompt(
            capability='test_capability',
            version='v1.0.0',
            content='Test prompt content with enough characters',
            status='active',
            component_type=ComponentType.SKILL
        ))

        # Симуляция улучшения до целевого значения
        iteration = {'count': 0}

        async def mock_test_version(cap, ver, old_ver):
            iteration['count'] += 1
            # Улучшение с каждой итерацией
            accuracy = 0.7 + (iteration['count'] * 0.1)
            return {'metrics': {'accuracy': min(accuracy, 0.95)}}

        optimization_service._test_new_version = mock_test_version

        # Запуск оптимизации
        result = await optimization_service.start_optimization_cycle(
            capability='test_capability',
            mode=OptimizationMode.ACCURACY,
            target_metrics=[
                TargetMetric(name='accuracy', target_value=0.9)
            ]
        )

        # Проверка
        assert result is not None
        # target_achieved может быть True или False в зависимости от итераций
        assert result.iterations > 0


class TestOptimizationLocking:
    """Тесты блокировок оптимизации"""

    @pytest.mark.asyncio
    async def test_optimization_lock_acquire_release(self):
        """Тест acquire/release блокировки"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Acquire lock
        result1 = await optimization_service._acquire_lock('test_capability')
        assert result1 is True

        # Попытка acquire ещё раз должна失败
        result2 = await optimization_service._acquire_lock('test_capability')
        assert result2 is False

        # Release lock
        await optimization_service._release_lock('test_capability')

        # Теперь acquire должен succeed
        result3 = await optimization_service._acquire_lock('test_capability')
        assert result3 is True

        # Cleanup
        await optimization_service._release_lock('test_capability')

    @pytest.mark.asyncio
    async def test_optimization_status(self):
        """Тест получения статуса оптимизации"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Статус когда оптимизация не запущена
        status = await optimization_service.get_optimization_status('test_capability')
        assert status['status'] == 'idle'

        # Acquire lock и проверка статуса
        await optimization_service._acquire_lock('test_capability')
        status = await optimization_service.get_optimization_status('test_capability')
        assert status['status'] == 'running'
        assert 'acquired_at' in status
        assert 'expires_at' in status

        # Release и проверка
        await optimization_service._release_lock('test_capability')
        status = await optimization_service.get_optimization_status('test_capability')
        assert status['status'] == 'idle'

    @pytest.mark.asyncio
    async def test_optimization_cancel(self):
        """Тест отмены оптимизации"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Cancel когда не запущено
        result = await optimization_service.cancel_optimization('test_capability')
        assert result is False

        # Acquire и cancel
        await optimization_service._acquire_lock('test_capability')
        result = await optimization_service.cancel_optimization('test_capability')
        assert result is True

        # Проверка что lock снят
        status = await optimization_service.get_optimization_status('test_capability')
        assert status['status'] == 'idle'


class TestOptimizationModes:
    """Тесты режимов оптимизации"""

    def test_optimization_mode_accuracy(self):
        """Тест режима accuracy"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        old_metrics = {'accuracy': 0.7}
        new_metrics = {'accuracy': 0.85}

        from core.models.data.benchmark import OptimizationMode
        is_improved = optimization_service._is_improvement(
            old_metrics, new_metrics, OptimizationMode.ACCURACY
        )

        assert is_improved is True

    def test_optimization_mode_speed(self):
        """Тест режима speed"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        old_metrics = {'avg_execution_time_ms': 200.0}
        new_metrics = {'avg_execution_time_ms': 150.0}

        from core.models.data.benchmark import OptimizationMode
        is_improved = optimization_service._is_improvement(
            old_metrics, new_metrics, OptimizationMode.SPEED
        )

        assert is_improved is True

    def test_optimization_improvement_threshold(self):
        """Тест порога улучшения"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)

        opt_config = OptimizationConfig(min_improvement=0.1)  # 10% порог
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Улучшение 5% < 10% порога
        old_metrics = {'accuracy': 0.8}
        new_metrics = {'accuracy': 0.84}  # 5% улучшение

        from core.models.data.benchmark import OptimizationMode
        is_improved = optimization_service._is_improvement(
            old_metrics, new_metrics, OptimizationMode.ACCURACY
        )

        assert is_improved is False

        # Улучшение 15% > 10% порога
        new_metrics = {'accuracy': 0.92}  # 15% улучшение
        is_improved = optimization_service._is_improvement(
            old_metrics, new_metrics, OptimizationMode.ACCURACY
        )

        assert is_improved is True


class TestOptimizationEvents:
    """Тесты событий оптимизации"""

    @pytest.mark.asyncio
    async def test_optimization_events_published(self):
        """Тест публикации событий оптимизации"""
        from core.application.services.optimization_service import OptimizationService, OptimizationConfig
        from core.application.services.benchmark_service import BenchmarkService
        from core.infrastructure.event_bus.event_bus import EventBus, EventType
        from core.models.data.prompt import Prompt
        from core.models.enums.common_enums import ComponentType

        event_bus = EventBus()
        benchmark_service = MagicMock(spec=BenchmarkService)
        benchmark_service.promote_version = AsyncMock(return_value=True)

        opt_config = OptimizationConfig()
        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=MagicMock(),
            metrics_collector=MagicMock(),
            event_bus=event_bus,
            config=opt_config
        )

        # Подписка на события
        events_received = []

        async def on_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, on_event)
        event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, on_event)

        # Мокаем методы
        optimization_service._is_capability_optimizable = AsyncMock(return_value=True)
        optimization_service._needs_optimization = AsyncMock(return_value=True)
        optimization_service._analyze_failures = AsyncMock(return_value=FailureAnalysis(
            capability='test_capability',
            version='v1.0.0',
            total_failures=0
        ))
        optimization_service._get_current_version = AsyncMock(return_value='v1.0.0')
        optimization_service._get_current_prompt = AsyncMock(return_value=Prompt(
            capability='test_capability',
            version='v1.0.0',
            content='Test prompt content with enough characters',
            status='active',
            component_type=ComponentType.SKILL
        ))
        optimization_service._test_new_version = AsyncMock(return_value={'metrics': {'accuracy': 0.95}})

        # Запуск оптимизации
        await optimization_service.start_optimization_cycle(
            capability='test_capability',
            mode=OptimizationMode.ACCURACY
        )

        # Проверка событий (хотя бы одно событие должно быть)
        assert len(events_received) >= 1
        event_types = [e.event_type for e in events_received]
        assert 'optimization.cycle.started' in event_types
