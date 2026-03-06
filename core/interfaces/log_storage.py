"""
Интерфейс для хранилища логов.
"""

from typing import Protocol, Dict, Any, Optional, List
from datetime import datetime


class LogStorageInterface(Protocol):
    """Интерфейс для хранилища логов."""

    async def save(
        self,
        level: str,
        message: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Сохранение лога.

        ARGS:
        - level: Уровень логирования
        - message: Сообщение
        - timestamp: Время события
        - metadata: Дополнительные метаданные
        """
        ...

    async def get(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получение логов за период.

        ARGS:
        - start_time: Начало периода
        - end_time: Конец периода
        - level: Фильтр по уровню
        - limit: Максимальное количество записей

        RETURNS:
        - Список записей логов
        """
        ...

    async def delete(
        self,
        older_than: Optional[datetime] = None
    ) -> int:
        """
        Удаление старых логов.

        ARGS:
        - older_than: Удалить старше этой даты

        RETURNS:
        - Количество удалённых записей
        """
        ...
