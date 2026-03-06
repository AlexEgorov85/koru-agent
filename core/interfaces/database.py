"""
Интерфейс для работы с базой данных.

Определяет контракт для всех реализаций БД (PostgreSQL, SQLite, и т.д.).
"""

from typing import Protocol, List, Dict, Any, Optional, Callable, Awaitable


class DatabaseInterface(Protocol):
    """
    Интерфейс для работы с базой данных.

    АБСТРАКЦИЯ: Определяет что нужно для работы с БД.
    РЕАЛИЗАЦИИ: PostgreSQLProvider, SQLiteProvider, MockDBProvider.
    """

    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполнить SELECT запрос.

        ARGS:
        - sql: SQL запрос
        - params: Параметры запроса

        RETURNS:
        - Список строк результата
        """
        ...

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Выполнить INSERT/UPDATE/DELETE запрос.

        ARGS:
        - sql: SQL запрос
        - params: Параметры запроса

        RETURNS:
        - Количество затронутых строк
        """
        ...

    async def transaction(
        self,
        operations: List[Callable[[], Awaitable[Any]]]
    ) -> Any:
        """
        Выполнить операции в транзакции.

        ARGS:
        - operations: Список асинхронных операций

        RETURNS:
        - Результат последней операции
        """
        ...

    async def close(self) -> None:
        """Закрыть соединение."""
        ...
