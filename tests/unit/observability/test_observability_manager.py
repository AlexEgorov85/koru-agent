"""
Тесты для Observability Manager.

TESTS:
- test_observability_creation: Создание менеджера
- test_record_operation: Запись операций
- test_health_checker: Проверка здоровья
- test_stats: Статистика
- test_dashboard_data: Данные для дашборда
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.observability import (
    ObservabilityManager,
    HealthChecker,
    HealthStatus,
    ComponentType,
    HealthCheckResult,
    OperationMetrics,
    get_observability_manager,
    create_observability_manager,
    reset_observability_manager,
)
from core.infrastructure.event_bus import reset_event_bus_manager


@pytest.fixture
def observability_manager():
    """Фикстура: менеджер наблюдаемости."""
    reset_observability_manager()
    reset_event_bus_manager()
    manager = ObservabilityManager()
    yield manager
    reset_observability_manager()
    reset_event_bus_manager()


class TestObservabilityManagerCreation:
    """Тесты создания менеджера."""

    def test_create_observability_manager(self):
        """Создание менеджера наблюдаемости."""
        manager = ObservabilityManager()
        
        assert manager is not None
        assert manager.health_checker is not None
        assert manager.metrics_collector is None  # Без хранилищ

    def test_get_observability_manager_singleton(self):
        """get_observability_manager возвращает singleton."""
        reset_observability_manager()
        
        manager1 = get_observability_manager()
        manager2 = get_observability_manager()
        
        assert manager1 is manager2

    def test_reset_observability_manager(self):
        """Сброс singleton."""
        reset_observability_manager()
        manager1 = get_observability_manager()
        
        reset_observability_manager()
        manager2 = get_observability_manager()
        
        assert manager1 is not manager2


class TestRecordOperation:
    """Тесты записи операций."""

    @pytest.mark.asyncio
    async def test_record_operation_success(self, observability_manager):
        """Запись успешной операции."""
        await observability_manager.record_operation(
            operation="test_op",
            component="test_component",
            duration_ms=100.5,
            success=True,
        )
        
        stats = observability_manager.get_stats()
        
        assert stats["operations"]["total"] == 1
        assert stats["operations"]["success"] == 1
        assert stats["operations"]["errors"] == 0
        assert stats["operations"]["avg_duration_ms"] == 100.5

    @pytest.mark.asyncio
    async def test_record_operation_error(self, observability_manager):
        """Запись ошибочной операции."""
        await observability_manager.record_operation(
            operation="test_op",
            component="test_component",
            duration_ms=50.0,
            success=False,
        )
        
        stats = observability_manager.get_stats()
        
        assert stats["operations"]["total"] == 1
        assert stats["operations"]["success"] == 0
        assert stats["operations"]["errors"] == 1

    @pytest.mark.asyncio
    async def test_record_multiple_operations(self, observability_manager):
        """Запись нескольких операций."""
        await observability_manager.record_operation("op1", "comp1", 100, True)
        await observability_manager.record_operation("op2", "comp1", 200, True)
        await observability_manager.record_operation("op3", "comp2", 150, False)
        
        stats = observability_manager.get_stats()
        
        assert stats["operations"]["total"] == 3
        assert stats["operations"]["success"] == 2
        assert stats["operations"]["errors"] == 1
        assert abs(stats["operations"]["avg_duration_ms"] - 150.0) < 0.01

    @pytest.mark.asyncio
    async def test_recent_operations(self, observability_manager):
        """Получение последних операций."""
        for i in range(10):
            await observability_manager.record_operation(
                f"op{i}", "comp", 100, True
            )
        
        recent = observability_manager.get_recent_operations(limit=5)
        
        assert len(recent) == 5
        assert recent[-1]["operation"] == "op9"


class TestHealthChecker:
    """Тесты проверки здоровья."""

    def test_health_checker_creation(self):
        """Создание HealthChecker."""
        checker = HealthChecker()
        
        assert checker is not None
        assert len(checker._checks) == 0

    @pytest.mark.asyncio
    async def test_register_health_check(self):
        """Регистрация проверки здоровья."""
        checker = HealthChecker()
        
        async def healthy_check():
            return True
        
        checker.register_check("test_check", healthy_check)
        
        assert "test_check" in checker._checks

    @pytest.mark.asyncio
    async def test_check_all_healthy(self):
        """Проверка здоровых компонентов."""
        checker = HealthChecker()
        
        checker.register_check("healthy", lambda: True)
        checker.register_check("also_healthy", lambda: {"status": "ok"})
        
        results = await checker.check_all()
        
        assert len(results) == 2
        assert results["healthy"].status == HealthStatus.HEALTHY
        assert results["also_healthy"].status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_unhealthy(self):
        """Проверка нездорового компонента."""
        checker = HealthChecker()
        
        async def unhealthy_check():
            raise Exception("Component is down")
        
        checker.register_check("unhealthy", unhealthy_check)
        
        results = await checker.check_all()
        
        assert "unhealthy" in results
        assert results["unhealthy"].status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_overall_status_healthy(self):
        """Общий статус когда все здорово."""
        checker = HealthChecker()
        
        checker.register_check("check1", lambda: True)
        checker.register_check("check2", lambda: True)
        
        await checker.check_all()
        
        assert checker.get_overall_status() == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_overall_status_unhealthy(self):
        """Общий статус когда есть нездоровые."""
        checker = HealthChecker()
        
        checker.register_check("healthy", lambda: True)
        checker.register_check("unhealthy", lambda: (_ for _ in ()).throw(Exception("Error")))
        
        await checker.check_all()
        
        assert checker.get_overall_status() == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_result_to_dict(self):
        """Конвертация результата в dict."""
        result = HealthCheckResult(
            component_name="test",
            component_type=ComponentType.PROVIDER,
            status=HealthStatus.HEALTHY,
            latency_ms=10.5,
        )
        
        data = result.to_dict()
        
        assert data["component_name"] == "test"
        assert data["status"] == "healthy"
        assert data["latency_ms"] == 10.5


class TestObservabilityStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_get_stats(self, observability_manager):
        """Получение статистики."""
        await observability_manager.record_operation("op1", "comp1", 100, True)
        await observability_manager.record_operation("op2", "comp1", 200, False)
        
        stats = observability_manager.get_stats()
        
        assert "operations" in stats
        assert "health" in stats
        assert "collectors" in stats
        assert stats["operations"]["total"] == 2
        assert stats["operations"]["success_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_get_dashboard_data(self, observability_manager):
        """Получение данных для дашборда."""
        await observability_manager.record_operation("op1", "comp1", 100, True)
        await observability_manager.record_operation("op2", "comp2", 200, True)
        await observability_manager.record_operation("op3", "comp1", 150, False)
        
        dashboard = await observability_manager.get_dashboard_data()
        
        assert "timestamp" in dashboard
        assert "summary" in dashboard
        assert "health" in dashboard
        assert "by_component" in dashboard
        assert "recent_operations" in dashboard
        
        # Проверка группировки по компонентам
        assert "comp1" in dashboard["by_component"]
        assert "comp2" in dashboard["by_component"]
        assert dashboard["by_component"]["comp1"]["total"] == 2
        assert dashboard["by_component"]["comp2"]["total"] == 1


class TestHealthMonitoring:
    """Тесты мониторинга здоровья."""

    @pytest.mark.asyncio
    async def test_start_stop_periodic_checks(self):
        """Запуск и остановка периодических проверок."""
        checker = HealthChecker()
        
        checker.register_check("test", lambda: True)
        
        await checker.start_periodic_checks(interval=0.1)
        
        # Даем время на несколько проверок
        await asyncio.sleep(0.3)
        
        await checker.stop_periodic_checks()
        
        assert not checker._running

    @pytest.mark.asyncio
    async def test_periodic_checks_update_results(self):
        """Периодические проверки обновляют результаты."""
        checker = HealthChecker()
        
        check_count = [0]
        
        def counting_check():
            check_count[0] += 1
            return True
        
        checker.register_check("counting", counting_check)
        
        await checker.start_periodic_checks(interval=0.05)
        await asyncio.sleep(0.15)
        await checker.stop_periodic_checks()
        
        assert check_count[0] >= 2


class TestOperationMetrics:
    """Тесты метрик операций."""

    def test_operation_metrics_creation(self):
        """Создание метрик операции."""
        metrics = OperationMetrics(
            operation="test",
            component="comp",
            duration_ms=100.0,
            success=True,
        )
        
        assert metrics.operation == "test"
        assert metrics.component == "comp"
        assert metrics.duration_ms == 100.0
        assert metrics.success is True

    def test_operation_metrics_to_dict(self):
        """Конвертация в dict."""
        metrics = OperationMetrics(
            operation="test",
            component="comp",
            duration_ms=100.0,
            success=True,
            metadata={"key": "value"},
        )
        
        data = metrics.to_dict()
        
        assert data["operation"] == "test"
        assert data["duration_ms"] == 100.0
        assert data["metadata"]["key"] == "value"


class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, observability_manager):
        """Полный рабочий цикл."""
        # Инициализация
        await observability_manager.initialize()

        # Регистрация проверок здоровья
        observability_manager.register_health_check("db", lambda: True)
        observability_manager.register_health_check("cache", lambda: True)

        # Запись операций
        await observability_manager.record_operation("query", "db", 50, True)
        await observability_manager.record_operation("cache_get", "cache", 10, True)
        await observability_manager.record_operation("query", "db", 60, False)

        # Проверка здоровья
        health = await observability_manager.get_health_status()
        assert len(health) == 2

        # Статистика
        stats = observability_manager.get_stats()
        assert stats["operations"]["total"] == 3

        # Дашборд
        dashboard = await observability_manager.get_dashboard_data()
        assert dashboard["summary"]["total"] == 3

        # Завершение
        await observability_manager.shutdown()


class TestObservabilityManagerCoverage:
    """Тесты для покрытия недостающих строк."""

    @pytest.mark.asyncio
    async def test_unregister_health_check(self, observability_manager):
        """Тест: Удаление проверки здоровья."""
        observability_manager.register_health_check("test", lambda: True)
        assert "test" in observability_manager.health_checker._checks

        observability_manager.health_checker.unregister_check("test")
        assert "test" not in observability_manager.health_checker._checks

    @pytest.mark.asyncio
    async def test_record_error(self, observability_manager):
        """Тест: Запись ошибки."""
        error = ValueError("Test error")
        await observability_manager.record_error(
            error=error,
            component="test_component",
            operation="test_operation",
            metadata={"key": "value"},
        )
        # Проверяем что метод выполнился без ошибок
        # (если бы была ошибка, тест упал бы выше)
        assert True

    @pytest.mark.asyncio
    async def test_get_recent_operations_limit(self, observability_manager):
        """Тест: Ограничение recent operations."""
        for i in range(150):  # Больше max_recent_operations (100)
            await observability_manager.record_operation(
                f"op{i}", "comp", 100, True
            )

        recent = observability_manager.get_recent_operations(limit=20)

        assert len(recent) == 20
        assert recent[-1]["operation"] == "op149"

    @pytest.mark.asyncio
    async def test_dashboard_data_grouping(self, observability_manager):
        """Тест: Группировка в dashboard data."""
        await observability_manager.record_operation("op1", "comp1", 100, True)
        await observability_manager.record_operation("op2", "comp1", 200, True)
        await observability_manager.record_operation("op3", "comp2", 150, False)

        dashboard = await observability_manager.get_dashboard_data()

        assert "comp1" in dashboard["by_component"]
        assert "comp2" in dashboard["by_component"]
        assert dashboard["by_component"]["comp1"]["total"] == 2
        assert dashboard["by_component"]["comp2"]["total"] == 1
        assert dashboard["by_component"]["comp1"]["success_rate"] == 100.0
        assert dashboard["by_component"]["comp2"]["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_shutdown(self, observability_manager):
        """Тест: Завершение работы."""
        await observability_manager.initialize()
        await observability_manager.start_health_monitoring(interval=0.1)

        await observability_manager.shutdown()

        assert observability_manager.health_checker._running is False

    @pytest.mark.asyncio
    async def test_get_overall_status_unknown(self):
        """Тест: Общий статус UNKNOWN."""
        checker = HealthChecker()
        # Без результатов проверок
        assert checker.get_overall_status() == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_all_exception_handling(self):
        """Тест: Обработка исключений в check_all."""
        checker = HealthChecker()

        def raising_check():
            raise RuntimeError("Unexpected error")

        checker.register_check("raising", raising_check)

        results = await checker.check_all()

        assert "raising" in results
        assert results["raising"].status == HealthStatus.UNHEALTHY
        assert "Unexpected error" in results["raising"].message

    @pytest.mark.asyncio
    async def test_get_overall_status_degraded(self):
        """Тест: Общий статус DEGRADED."""
        checker = HealthChecker()

        checker.register_check("healthy", lambda: HealthCheckResult(
            component_name="healthy",
            component_type=ComponentType.PROVIDER,
            status=HealthStatus.HEALTHY,
        ))
        checker.register_check("degraded", lambda: HealthCheckResult(
            component_name="degraded",
            component_type=ComponentType.PROVIDER,
            status=HealthStatus.DEGRADED,
        ))

        await checker.check_all()

        assert checker.get_overall_status() == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all_returns_health_check_result(self):
        """Тест: check_all возвращает HealthCheckResult."""
        checker = HealthChecker()

        async def returning_check():
            return HealthCheckResult(
                component_name="test",
                component_type=ComponentType.SERVICE,
                status=HealthStatus.HEALTHY,
                message="All good",
                latency_ms=5.0,
            )

        checker.register_check("test", returning_check)

        results = await checker.check_all()

        assert "test" in results
        assert results["test"].status == HealthStatus.HEALTHY
        assert results["test"].message == "All good"
        assert results["test"].latency_ms >= 0

    @pytest.mark.asyncio
    async def test_start_health_monitoring(self, observability_manager):
        """Тест: Запуск мониторинга здоровья."""
        await observability_manager.start_health_monitoring(interval=0.1)

        # Даем время на запуск
        await asyncio.sleep(0.15)

        assert observability_manager.health_checker._running is True

        await observability_manager.health_checker.stop_periodic_checks()

    @pytest.mark.asyncio
    async def test_create_and_reset_observability_manager(self):
        """Тест: create и reset observability manager."""
        reset_observability_manager()
        reset_event_bus_manager()

        manager = create_observability_manager()

        assert manager is not None
        assert isinstance(manager, ObservabilityManager)

        # Проверяем что singleton установлен
        manager2 = get_observability_manager()
        assert manager is manager2

        # Сбрасываем
        reset_observability_manager()
        manager3 = get_observability_manager()
        assert manager3 is not manager

    @pytest.mark.asyncio
    async def test_get_overall_status_unknown_with_mixed_results(self):
        """Тест: Общий статус UNKNOWN при смешанных результатах."""
        checker = HealthChecker()

        # Создаём результаты которые не попадают в HEALTHY/UNHEALTHY/DEGRADED
        # Это покрытие для else ветки в get_overall_status
        checker._last_results = {
            "test": HealthCheckResult(
                component_name="test",
                component_type=ComponentType.PROVIDER,
                status=HealthStatus.UNKNOWN,  # UNKNOWN статус
            )
        }

        # Должен вернуться UNKNOWN т.к. нет HEALTHY/UNHEALTHY/DEGRADED
        assert checker.get_overall_status() == HealthStatus.UNKNOWN


class TestObservabilityManagerWithStorages:
    """Тесты ObservabilityManager с хранилищами."""

    @pytest.mark.asyncio
    async def test_initialize_with_metrics_storage(self):
        """Тест: Инициализация с metrics storage."""
        from unittest.mock import AsyncMock, MagicMock
        from core.infrastructure.metrics_collector import MetricsCollector

        reset_observability_manager()
        reset_event_bus_manager()

        # Создаём mock хранилища
        mock_metrics_storage = MagicMock()
        mock_metrics_storage.record = AsyncMock()
        mock_metrics_storage.get_records = AsyncMock(return_value=[])
        mock_metrics_storage.aggregate = AsyncMock(return_value={})
        mock_metrics_storage.clear_old = AsyncMock()

        manager = ObservabilityManager(metrics_storage=mock_metrics_storage)
        await manager.initialize()

        # Проверяем что MetricsCollector был создан
        assert manager.metrics_collector is not None
        assert isinstance(manager.metrics_collector, MetricsCollector)

        await manager.shutdown()
        reset_observability_manager()
        reset_event_bus_manager()

    @pytest.mark.asyncio
    async def test_initialize_with_log_storage(self):
        """Тест: Инициализация с log storage."""
        from unittest.mock import AsyncMock, MagicMock
        from core.infrastructure.log_collector import LogCollector

        reset_observability_manager()
        reset_event_bus_manager()

        # Создаём mock хранилища
        mock_log_storage = MagicMock()
        mock_log_storage.save = AsyncMock()
        mock_log_storage.get_by_session = AsyncMock(return_value=[])
        mock_log_storage.get_by_capability = AsyncMock(return_value=[])
        mock_log_storage.clear_old = AsyncMock()

        manager = ObservabilityManager(log_storage=mock_log_storage)
        await manager.initialize()

        # Проверяем что LogCollector был создан
        assert manager.log_collector is not None
        assert isinstance(manager.log_collector, LogCollector)

        await manager.shutdown()
        reset_observability_manager()
        reset_event_bus_manager()

    @pytest.mark.asyncio
    async def test_initialize_with_both_storages(self):
        """Тест: Инициализация с обоими хранилищами."""
        from unittest.mock import AsyncMock, MagicMock

        reset_observability_manager()
        reset_event_bus_manager()

        # Создаём mock хранилища
        mock_metrics_storage = MagicMock()
        mock_metrics_storage.record = AsyncMock()
        mock_metrics_storage.get_records = AsyncMock(return_value=[])
        mock_metrics_storage.aggregate = AsyncMock(return_value={})
        mock_metrics_storage.clear_old = AsyncMock()

        mock_log_storage = MagicMock()
        mock_log_storage.save = AsyncMock()
        mock_log_storage.get_by_session = AsyncMock(return_value=[])
        mock_log_storage.get_by_capability = AsyncMock(return_value=[])
        mock_log_storage.clear_old = AsyncMock()

        manager = ObservabilityManager(
            metrics_storage=mock_metrics_storage,
            log_storage=mock_log_storage
        )
        await manager.initialize()

        # Проверяем что оба коллектора были созданы
        assert manager.metrics_collector is not None
        assert manager.log_collector is not None

        await manager.shutdown()
        reset_observability_manager()
        reset_event_bus_manager()


class TestHealthCheckerEdgeCases:
    """Тесты граничных случаев HealthChecker."""

    @pytest.mark.asyncio
    async def test_periodic_check_loop_exception_handling(self):
        """Тест: Обработка исключений в периодическом цикле проверок."""
        from unittest.mock import patch

        checker = HealthChecker()

        call_count = [0]

        def check_that_raises():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First call fails")
            return True

        checker.register_check("flaky", check_that_raises)

        with patch.object(checker._logger, 'error') as mock_logger:
            await checker.start_periodic_checks(interval=0.05)

            # Ждём несколько итераций цикла
            await asyncio.sleep(0.15)

            await checker.stop_periodic_checks()

            # Проверяем что ошибка была залогирована
            assert mock_logger.called
            # И цикл продолжил работу
            assert call_count[0] >= 2
