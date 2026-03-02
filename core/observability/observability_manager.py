"""
Менеджер наблюдаемости (Observability Manager).

АРХИТЕКТУРА:
- Единая точка для метрик, логов и трассировки
- Health Checker для проверки здоровья компонентов
- Агрегация данных наблюдаемости
- Интеграция с Event Bus для событий

ПРЕИМУЩЕСТВА:
- ✅ Единый интерфейс для всей наблюдаемости
- ✅ Корреляция метрик, логов и трассировки
- ✅ Health check всех компонентов
- ✅ Готовые дашборды и алерты
"""
import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.log_collector import LogCollector
from core.infrastructure.interfaces.metrics_log_interfaces import (
    IMetricsStorage,
    ILogStorage,
)


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Статус здоровья компонента."""
    HEALTHY = "healthy"       # Все работает нормально
    DEGRADED = "degraded"     # Частичная деградация
    UNHEALTHY = "unhealthy"   # Критическая ошибка
    UNKNOWN = "unknown"       # Статус неизвестен


class ComponentType(Enum):
    """Тип компонента для наблюдаемости."""
    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"
    SERVICE = "service"
    PROVIDER = "provider"
    BEHAVIOR = "behavior"


@dataclass
class HealthCheckResult:
    """Результат проверки здоровья."""
    component_name: str
    component_type: ComponentType
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    last_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "component_name": self.component_name,
            "component_type": self.component_type.value,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class OperationMetrics:
    """Метрики операции."""
    operation: str
    component: str
    duration_ms: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "operation": self.operation,
            "component": self.component,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class HealthChecker:
    """
    Проверка здоровья компонентов.
    
    FEATURES:
    - Регистрация проверок здоровья
    - Периодическая проверка
    - Агрегация статусов
    """
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 30.0  # секунд
        
        self._logger = logging.getLogger(f"{__name__}.HealthChecker")
    
    def register_check(self, name: str, check_fn: Callable):
        """
        Регистрация проверки здоровья.
        
        ARGS:
        - name: имя проверки
        - check_fn: функция проверки (async или sync)
        """
        self._checks[name] = check_fn
        self._logger.debug(f"Зарегистрирована проверка здоровья: {name}")
    
    def unregister_check(self, name: str):
        """Удаление проверки здоровья."""
        if name in self._checks:
            del self._checks[name]
            self._logger.debug(f"Удалена проверка здоровья: {name}")
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Проверка здоровья всех компонентов.
        
        RETURNS:
        - Dict[str, HealthCheckResult]: результаты проверок
        """
        results = {}
        
        for name, check_fn in self._checks.items():
            try:
                start_time = time.time()
                
                if inspect.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    result = check_fn()
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Преобразование результата в HealthCheckResult
                if isinstance(result, HealthCheckResult):
                    results[name] = result
                elif isinstance(result, bool):
                    results[name] = HealthCheckResult(
                        component_name=name,
                        component_type=ComponentType.PROVIDER,
                        status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                        latency_ms=latency_ms,
                    )
                else:
                    results[name] = HealthCheckResult(
                        component_name=name,
                        component_type=ComponentType.PROVIDER,
                        status=HealthStatus.HEALTHY,
                        latency_ms=latency_ms,
                        metadata={"result": result},
                    )
                    
            except Exception as e:
                results[name] = HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.PROVIDER,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                )
                self._logger.error(f"Проверка здоровья '{name}' не удалась: {e}")
        
        self._last_results = results
        return results
    
    async def start_periodic_checks(self, interval: float = 30.0):
        """Запуск периодических проверок."""
        self._check_interval = interval
        self._running = True
        self._task = asyncio.create_task(self._periodic_check_loop())
        self._logger.info(f"Запущены периодические проверки здоровья (interval={interval}s)")
    
    async def stop_periodic_checks(self):
        """Остановка периодических проверок."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Периодические проверки здоровья остановлены")
    
    async def _periodic_check_loop(self):
        """Цикл периодических проверок."""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Ошибка в цикле проверок здоровья: {e}")
                await asyncio.sleep(self._check_interval)
    
    def get_overall_status(self) -> HealthStatus:
        """Получение общего статуса здоровья."""
        if not self._last_results:
            return HealthStatus.UNKNOWN
        
        statuses = [r.status for r in self._last_results.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN


class ObservabilityManager:
    """
    Единая система наблюдаемости.
    
    FEATURES:
    - Метрики (MetricsCollector)
    - Логи (LogCollector)
    - Health Checker
    - Трассировка операций
    - Статистика и дашборды
    
    USAGE:
    ```python
    # Создание менеджера
    obs_manager = ObservabilityManager(
        event_bus_manager=event_bus_manager,
        metrics_storage=metrics_storage,
        log_storage=log_storage,
    )
    
    # Инициализация
    await obs_manager.initialize()
    
    # Запись операции
    await obs_manager.record_operation(
        operation="execute_skill",
        component="planning",
        duration_ms=150.5,
        success=True,
    )
    
    # Проверка здоровья
    health = await obs_manager.get_health_status()
    
    # Статистика
    stats = obs_manager.get_stats()
    ```
    """

    def __init__(
        self,
        event_bus=None,
        metrics_storage: Optional[IMetricsStorage] = None,
        log_storage: Optional[ILogStorage] = None,
    ):
        """
        Инициализация менеджера наблюдаемости.

        ARGS:
        - event_bus: шина событий
        - metrics_storage: хранилище метрик
        - log_storage: хранилище логов
        """
        self._event_bus = event_bus
        self._metrics_storage = metrics_storage
        self._log_storage = log_storage
        
        # Компоненты наблюдаемости
        self.metrics_collector: Optional[MetricsCollector] = None
        self.log_collector: Optional[LogCollector] = None
        self.health_checker = HealthChecker()
        
        # Счетчики операций
        self._operation_count = 0
        self._success_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        
        # История операций (для отладки)
        self._recent_operations: List[OperationMetrics] = []
        self._max_recent_operations = 100
        
        self._logger = logging.getLogger(f"{__name__}.ObservabilityManager")
        self._logger.info("ObservabilityManager создан")
    
    async def initialize(self):
        """Инициализация компонентов наблюдаемости."""
        self._logger.info("Инициализация ObservabilityManager")
        
        # Инициализация сборщиков если есть хранилища
        if self._metrics_storage:
            event_bus = self._event_bus.get_bus(EventDomain.INFRASTRUCTURE)._event_bus
            self.metrics_collector = MetricsCollector(
                event_bus=event_bus,
                storage=self._metrics_storage,
            )
            await self.metrics_collector.initialize()
            self._logger.debug("MetricsCollector инициализирован")
        
        if self._log_storage:
            event_bus = self._event_bus.get_bus(EventDomain.INFRASTRUCTURE)._event_bus
            self.log_collector = LogCollector(
                event_bus=event_bus,
                storage=self._log_storage,
            )
            await self.log_collector.initialize()
            self._logger.debug("LogCollector инициализирован")
        
        self._logger.info("ObservabilityManager инициализирован")
    
    async def shutdown(self):
        """Завершение работы компонентов наблюдаемости."""
        self._logger.info("Завершение работы ObservabilityManager")
        
        if self.health_checker:
            await self.health_checker.stop_periodic_checks()
        
        self._logger.info("ObservabilityManager завершен")
    
    async def record_operation(
        self,
        operation: str,
        component: str,
        duration_ms: float,
        success: bool,
        metadata: Dict[str, Any] = None,
    ):
        """
        Запись операции во все системы наблюдаемости.
        
        ARGS:
        - operation: имя операции
        - component: компонент где выполнена операция
        - duration_ms: длительность в миллисекундах
        - success: успешность выполнения
        - metadata: дополнительные метаданные
        """
        self._operation_count += 1
        if success:
            self._success_count += 1
        else:
            self._error_count += 1
        self._total_duration_ms += duration_ms
        
        # Создание метрики операции
        op_metrics = OperationMetrics(
            operation=operation,
            component=component,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {},
        )
        
        # Сохранение в историю
        self._recent_operations.append(op_metrics)
        if len(self._recent_operations) > self._max_recent_operations:
            self._recent_operations.pop(0)
        
        # Публикация события метрики
        await self._event_bus.publish(
            EventType.METRIC_COLLECTED,
            data=op_metrics.to_dict(),
            domain=EventDomain.COMMON,
        )
        
        # Логирование ошибки если не успешно
        if not success:
            await self._event_bus.publish(
                EventType.ERROR_OCCURRED,
                data={
                    "operation": operation,
                    "component": component,
                    "duration_ms": duration_ms,
                    "metadata": metadata or {},
                },
                domain=EventDomain.COMMON,
            )
    
    async def record_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        metadata: Dict[str, Any] = None,
    ):
        """
        Запись ошибки.
        
        ARGS:
        - error: объект ошибки
        - component: компонент где произошла ошибка
        - operation: операция которая выполнялась
        - metadata: дополнительные метаданные
        """
        await self._event_bus.publish(
            EventType.ERROR_OCCURRED,
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "component": component,
                "operation": operation,
                "metadata": metadata or {},
            },
            domain=EventDomain.COMMON,
        )
    
    def register_health_check(self, name: str, check_fn: Callable):
        """
        Регистрация проверки здоровья.
        
        ARGS:
        - name: имя проверки
        - check_fn: функция проверки
        """
        self.health_checker.register_check(name, check_fn)
        self._logger.debug(f"Зарегистрирована проверка здоровья: {name}")
    
    async def get_health_status(self) -> Dict[str, HealthCheckResult]:
        """
        Получение статуса здоровья всех компонентов.
        
        RETURNS:
        - Dict[str, HealthCheckResult]: результаты проверок
        """
        return await self.health_checker.check_all()
    
    async def start_health_monitoring(self, interval: float = 30.0):
        """
        Запуск мониторинга здоровья.
        
        ARGS:
        - interval: интервал проверок в секундах
        """
        await self.health_checker.start_periodic_checks(interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики наблюдаемости."""
        avg_duration = (
            self._total_duration_ms / self._operation_count
            if self._operation_count > 0 else 0.0
        )
        
        success_rate = (
            self._success_count / self._operation_count * 100
            if self._operation_count > 0 else 0.0
        )
        
        return {
            "operations": {
                "total": self._operation_count,
                "success": self._success_count,
                "errors": self._error_count,
                "success_rate": success_rate,
                "avg_duration_ms": avg_duration,
                "total_duration_ms": self._total_duration_ms,
            },
            "health": {
                "overall": self.health_checker.get_overall_status().value,
                "components": {
                    name: result.to_dict()
                    for name, result in self.health_checker._last_results.items()
                },
            },
            "collectors": {
                "metrics_initialized": self.metrics_collector is not None,
                "log_initialized": self.log_collector is not None,
            },
        }
    
    def get_recent_operations(self, limit: int = 10) -> List[Dict]:
        """Получение последних операций."""
        operations = self._recent_operations[-limit:]
        return [op.to_dict() for op in operations]
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Получение данных для дашборда.
        
        RETURNS:
        - Dict[str, Any]: данные для дашборда
        """
        stats = self.get_stats()
        
        # Группировка операций по компонентам
        by_component: Dict[str, Dict] = {}
        for op in self._recent_operations:
            if op.component not in by_component:
                by_component[op.component] = {
                    "total": 0,
                    "success": 0,
                    "errors": 0,
                    "total_duration_ms": 0.0,
                }
            
            by_component[op.component]["total"] += 1
            if op.success:
                by_component[op.component]["success"] += 1
            else:
                by_component[op.component]["errors"] += 1
            by_component[op.component]["total_duration_ms"] += op.duration_ms
        
        # Вычисление средних значений
        for comp_data in by_component.values():
            if comp_data["total"] > 0:
                comp_data["avg_duration_ms"] = (
                    comp_data["total_duration_ms"] / comp_data["total"]
                )
                comp_data["success_rate"] = (
                    comp_data["success"] / comp_data["total"] * 100
                )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": stats["operations"],
            "health": stats["health"],
            "by_component": by_component,
            "recent_operations": self.get_recent_operations(20),
        }


# Глобальный менеджер наблюдаемости (singleton)
_global_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """
    Получение глобального менеджера наблюдаемости.
    
    RETURNS:
    - ObservabilityManager: глобальный экземпляр
    """
    global _global_observability_manager
    if _global_observability_manager is None:
        _global_observability_manager = ObservabilityManager()
    return _global_observability_manager


def create_observability_manager(
    event_bus_manager: EventBusManager = None,
    metrics_storage: IMetricsStorage = None,
    log_storage: ILogStorage = None,
) -> ObservabilityManager:
    """
    Создание глобального менеджера наблюдаемости.
    
    ARGS:
    - event_bus_manager: менеджер событий
    - metrics_storage: хранилище метрик
    - log_storage: хранилище логов
    
    RETURNS:
    - ObservabilityManager: созданный экземпляр
    """
    global _global_observability_manager
    _global_observability_manager = ObservabilityManager(
        event_bus_manager=event_bus_manager,
        metrics_storage=metrics_storage,
        log_storage=log_storage,
    )
    return _global_observability_manager


def reset_observability_manager():
    """Сброс глобального менеджера (для тестов)."""
    global _global_observability_manager
    _global_observability_manager = None
