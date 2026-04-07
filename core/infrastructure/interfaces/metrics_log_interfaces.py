"""
Интерфейсы для хранилищ метрик и логов.

СОДЕРЖИТ:
- IMetricsStorage: интерфейс для хранилища метрик
- ILogStorage: интерфейс для хранилища логов
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple
from core.models.data.metrics import MetricRecord, AggregatedMetrics
from core.components.benchmarks.benchmark_models import LogEntry


class IMetricsStorage(ABC):
    """
    Интерфейс для хранилища метрик.

    RESPONSIBILITIES:
    - Запись метрик
    - Получение метрик по фильтрам
    - Агрегация метрик
    - Очистка старых метрик
    """

    @abstractmethod
    async def record(self, metric: MetricRecord) -> None:
        """
        Запись метрики в хранилище.

        ARGS:
        - metric: объект метрики для записи

        RETURNS:
        - None
        """
        pass

    @abstractmethod
    async def get_records(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[MetricRecord]:
        """
        Получение записей метрик по фильтрам.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта (опционально)
        - time_range: временной диапазон (start, end) (опционально)
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[MetricRecord]: список записей метрик
        """
        pass

    @abstractmethod
    async def aggregate(
        self,
        capability: str,
        version: str,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> AggregatedMetrics:
        """
        Агрегация метрик для бенчмарка.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта
        - time_range: временной диапазон (start, end) (опционально)

        RETURNS:
        - AggregatedMetrics: агрегированные метрики
        """
        pass

    @abstractmethod
    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых метрик.

        ARGS:
        - older_than: удалять метрики старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        pass


class ILogStorage(ABC):
    """
    Интерфейс для хранилища логов.

    RESPONSIBILITIES:
    - Сохранение логов
    - Получение логов по сессии
    - Получение логов по способности
    - Очистка старых логов
    """

    @abstractmethod
    async def save(self, entry: LogEntry) -> None:
        """
        Сохранение записи лога.

        ARGS:
        - entry: объект записи лога

        RETURNS:
        - None
        """
        pass

    @abstractmethod
    async def get_by_session(
        self,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов сессии.

        ARGS:
        - agent_id: идентификатор агента
        - session_id: идентификатор сессии
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        pass

    @abstractmethod
    async def get_by_capability(
        self,
        capability: str,
        log_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов по способности.

        ARGS:
        - capability: название способности
        - log_type: тип лога (опционально)
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        pass

    @abstractmethod
    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых логов.

        ARGS:
        - older_than: удалять логи старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        pass
