"""
Интерфейс для базы данных.

Определяет контракт для всех реализаций БД (PostgreSQL, SQLite, и т.д.).
"""

from typing import Protocol, Any, Optional, List, Dict, Union
from core.models.types.db_types import DBHealthStatus


class DatabaseInterface(Protocol):
    """
    Интерфейс для работы с базой данных.

    АБСТРАКЦИЯ: Определяет что нужно для работы с БД.
    РЕАЛИЗАЦИИ: PostgreSQLProvider, SQLiteProvider.
    """

    async def connect(self) -> None:
        """Подключение к базе данных."""
        ...

    async def disconnect(self) -> None:
        """Отключение от базы данных."""
        ...

    async def execute(
        self,
        query: str,
        params: Optional[Union[List, Dict]] = None
    ) -> int:
        """
        Выполнить SQL запрос (без возврата данных).

        ARGS:
        - query: SQL запрос
        - params: Параметры запроса

        RETURNS:
        - Количество затронутых строк
        """
        ...

    async def fetch_one(
        self,
        query: str,
        params: Optional[Union[List, Dict]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получить одну строку.

        ARGS:
        - query: SQL запрос
        - params: Параметры запроса

        RETURNS:
        - Словарь с данными или None
        """
        ...

    async def fetch_all(
        self,
        query: str,
        params: Optional[Union[List, Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить все строки.

        ARGS:
        - query: SQL запрос
        - params: Параметры запроса

        RETURNS:
        - Список словарей с данными
        """
        ...

    async def health_check(self) -> DBHealthStatus:
        """
        Проверка здоровья БД.

        RETURNS:
        - Статус здоровья
        """
        ...
