"""
Интерфейс для хранилища метрик.
"""

from typing import Protocol, Dict, Any, Optional, List
from datetime import datetime


class MetricsStorageInterface(Protocol):
    """Интерфейс для хранилища метрик."""

    async def save(
        self,
        metric_name: str,
        value: Any,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Сохранение метрики.

        ARGS:
        - metric_name: Имя метрики
        - value: Значение метрики
        - timestamp: Время измерения
        - metadata: Дополнительные метаданные
        """
        ...

    async def get(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение метрик за период.

        ARGS:
        - metric_name: Имя метрики
        - start_time: Начало периода
        - end_time: Конец периода

        RETURNS:
        - Список записей метрик
        """
        ...

    async def delete(
        self,
        metric_name: str,
        older_than: Optional[datetime] = None
    ) -> int:
        """
        Удаление метрик.

        ARGS:
        - metric_name: Имя метрики
        - older_than: Удалить старше этой даты

        RETURNS:
        - Количество удалённых записей
        """
        ...
