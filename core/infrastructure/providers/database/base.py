"""
Базовый класс для DB провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union, Optional
import time


class DBHealthStatus:
    """Статус здоровья DB провайдера."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BaseDBProvider(ABC):
    """
    Абстрактный базовый класс для всех DB провайдеров.
    """

    def __init__(self, config: Union[Dict[str, Any], Any]):
        """
        Инициализация DB провайдера.
        
        ПАРАМЕТРЫ:
        - config: Конфигурация подключения
        """
        # Сохраняем config как есть (dataclass или dict)
        self.config = config
        
        self.is_initialized = False
        self.health_status = DBHealthStatus.UNKNOWN
        self.last_health_check: Optional[float] = None
        self.creation_time = time.time()
        self.request_count = 0
        self.error_count = 0
        
        # event_bus_logger будет инициализирован в initialize()
        self.event_bus_logger = None

    @abstractmethod
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Выполнить SQL-запрос.

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            Результаты запроса в виде списка словарей
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить состояние провайдера.

        Returns:
            True если провайдер здоров
        """
        pass

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
                from core.infrastructure.event_bus.unified_logger import EventBusLogger
                event_bus = get_event_bus()
                self.event_bus_logger = EventBusLogger(event_bus, "system", "db_provider", "DB")
            except:
                self.event_bus_logger = type('obj', (object,), {
                    'info': lambda *args, **kwargs: None,
                    'debug': lambda *args, **kwargs: None,
                    'warning': lambda *args, **kwargs: None,
                    'error': lambda *args, **kwargs: None
                })()
        
        self.is_initialized = True
        self.health_status = DBHealthStatus.HEALTHY
        return True

    async def shutdown(self) -> None:
        """Завершение работы провайдера."""
        self.is_initialized = False
        self.health_status = DBHealthStatus.UNKNOWN
