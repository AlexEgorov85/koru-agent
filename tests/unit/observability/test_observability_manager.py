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
