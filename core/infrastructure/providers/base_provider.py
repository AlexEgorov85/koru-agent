"""
Базовый интерфейс и класс для всех провайдеров.

КОМПОНЕНТЫ:
- IProvider: интерфейс для всех провайдеров
- BaseProvider: базовая реализация с общей логикой

FEATURES:
- Единый интерфейс инициализации/shutdown/health_check
- Общая логика отслеживания состояния
- Базовые метрики производительности
- Поддержка политики повторных попыток
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.retry_policy.retry_and_error_policy import RetryPolicy

logger = logging.getLogger(__name__)


class ProviderHealthStatus:
    """Статус здоровья провайдера"""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class IProvider(ABC):
    """
    Интерфейс для всех провайдеров (LLM/DB/Vector/Embedding).

    МЕТОДЫ:
    - initialize(): Асинхронная инициализация провайдера
    - shutdown(): Корректное завершение работы
    - health_check(): Проверка состояния здоровья
    - restart(): Перезапуск провайдера
    - get_info(): Получение информации о провайдере
    """

    @abstractmethod
    async def initialize(self) -> bool:
        """Асинхронная инициализация провайдера."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы провайдера."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья провайдера."""
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Получение информации о провайдере."""
        pass


class BaseProvider(IProvider):
    """
    Базовый класс для всех провайдеров.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Инверсия зависимостей: Зависит только от абстракций
    2. Единый контракт: Все методы имеют стандартизированную сигнатуру
    3. Безопасность по умолчанию: Встроенные ограничения и валидация
    4. Наблюдаемость: Автоматическое логирование и метрики
    5. Отказоустойчивость: Грациозная деградация при ошибках

    USAGE:
        class MyProvider(BaseProvider):
            async def initialize(self) -> bool:
                # Инициализация
                self._set_healthy_status()
                return True

            async def shutdown(self) -> None:
                # Очистка ресурсов
                pass

            async def health_check(self) -> Dict[str, Any]:
                return {
                    "status": self.health_status,
                    "name": self.name
                }
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Инициализация провайдера.

        ПАРАМЕТРЫ:
        - name: Название провайдера
        - config: Конфигурация провайдера
        """
        self.name = name
        self.config = config or {}
        self.is_initialized = False
        self.health_status = ProviderHealthStatus.UNKNOWN
        self.last_health_check: Optional[float] = None
        self.creation_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.avg_response_time = 0.0
        self.retry_policy: Optional[RetryPolicy] = None

        # event_bus_logger будет инициализирован в initialize()
        self.event_bus_logger = None

    def _set_healthy_status(self) -> None:
        """Устанавливает статус здоровья как здоровый после успешной инициализации."""
        self.health_status = ProviderHealthStatus.HEALTHY
        self.last_health_check = time.time()

    def _set_degraded_status(self) -> None:
        """Устанавливает статус здоровья как degraded."""
        self.health_status = ProviderHealthStatus.DEGRADED
        self.last_health_check = time.time()

    def _set_unhealthy_status(self) -> None:
        """Устанавливает статус здоровья как unhealthy."""
        self.health_status = ProviderHealthStatus.UNHEALTHY
        self.last_health_check = time.time()

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация провайдера.

        ВОЗВРАЩАЕТ:
        - bool: True если инициализация успешна
        """
        # Инициализация event_bus_logger
        if self.event_bus_logger is None:
            try:
                from core.infrastructure.event_bus.unified_event_bus import get_event_bus
                from core.infrastructure.logging import EventBusLogger
                event_bus = get_event_bus()
                self.event_bus_logger = EventBusLogger(event_bus, "system", "provider", self.name)
            except:
                self.event_bus_logger = type('obj', (object,), {
                    'info': lambda *args, **kwargs: None,
                    'debug': lambda *args, **kwargs: None,
                    'warning': lambda *args, **kwargs: None,
                    'error': lambda *args, **kwargs: None
                })()

        self.is_initialized = True
        self._set_healthy_status()
        return True

    async def shutdown(self) -> None:
        """Корректное завершение работы провайдера."""
        self.is_initialized = False
        self.health_status = ProviderHealthStatus.UNKNOWN
        await self.event_bus_logger.info("Провайдер %s завершил работу", self.name)

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья провайдера.

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: информация о состоянии здоровья
        """
        self.last_health_check = time.time()
        return {
            "name": self.name,
            "status": self.health_status,
            "is_initialized": self.is_initialized,
            "last_check": self.last_health_check
        }

    async def restart(self) -> bool:
        """
        Перезапуск провайдера без полной перезагрузки системного контекста.

        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        try:
            await self.shutdown()
            return await self.initialize()
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка перезапуска провайдера: {str(e)}")
            return False

    def restart_with_module_reload(self):
        """
        Перезапуск провайдера с перезагрузкой модуля Python.
        ВНИМАНИЕ: Использовать с осторожностью!

        ВОЗВРАЩАЕТ:
        - Новый экземпляр провайдера из перезагруженного модуля
        """
        from core.utils.module_reloader import safe_reload_component_with_module_reload
        self.event_bus_logger.warning(
            f"Выполняется перезапуск с перезагрузкой модуля для провайдера {self.__class__.__name__}"
        )
        return safe_reload_component_with_module_reload(self)

    def _update_metrics(self, response_time: float, success: bool = True) -> None:
        """
        Обновление внутренних метрик провайдера.

        ПАРАМЕТРЫ:
        - response_time: время выполнения запроса
        - success: успешность выполнения
        """
        self.request_count += 1
        if not success:
            self.error_count += 1

        # Обновляем среднее время ответа с экспоненциальным сглаживанием
        alpha = 0.2
        self.avg_response_time = alpha * response_time + (1 - alpha) * self.avg_response_time

        # Обновляем состояние здоровья на основе ошибок
        if self.error_count > 0 and self.request_count > 1:
            error_rate = self.error_count / self.request_count
            if error_rate > 0.95:
                self._set_unhealthy_status()
            elif error_rate >= 0.5:
                self._set_degraded_status()

    def set_retry_policy(self, policy: RetryPolicy) -> None:
        """Установка политики повторных попыток."""
        self.retry_policy = policy

    def get_info(self) -> Dict[str, Any]:
        """
        Получение информации о провайдере.

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: информация о провайдере
        """
        return {
            "name": self.name,
            "provider_type": self.__class__.__name__,
            "is_initialized": self.is_initialized,
            "health_status": self.health_status,
            "uptime_seconds": time.time() - self.creation_time,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_response_time": self.avg_response_time
        }
