"""
Адаптеры для DatabasePort.

АДАПТЕРЫ = Реализации портов для конкретных технологий.
Использует существующие провайдеры через адаптер.
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable

from core.infrastructure.interfaces.ports import DatabasePort


class PostgreSQLAdapter(DatabasePort):
    """
    Адаптер PostgreSQL для DatabasePort.
    
    ОБЁРТКА вокруг PostgreSQLProvider для работы через порт.
    
    USAGE:
    ```python
    from core.infrastructure.providers.database.postgres_provider import PostgreSQLProvider
    
    provider = PostgreSQLProvider(config)
    await provider.initialize()
    
    adapter = PostgreSQLAdapter(provider)
    
    # Использование через порт
    rows = await adapter.query("SELECT * FROM books WHERE id = $1", {"id": 1})
    count = await adapter.execute("INSERT INTO logs (msg) VALUES ($1)", {"msg": "test"})
    ```
    """
    
    def __init__(self, provider):
        """
        ARGS:
        - provider: Экземпляр PostgreSQLProvider
        """
        self._provider = provider
    
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
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        # PostgreSQLProvider использует execute_query для SELECT
        return await self._provider.execute_query(sql, params)
    
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
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        # PostgreSQLProvider.execute возвращает DBQueryResult
        result = await self._provider.execute(sql, params)
        
        # Извлекаем количество затронутых строк
        if hasattr(result, 'rows_affected'):
            return result.rows_affected
        elif hasattr(result, 'rows'):
            return len(result.rows) if result.rows else 0
        else:
            # Fallback: пытаемся получить из result
            return getattr(result, 'count', 0)
    
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
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        # Используем контекстный менеджер транзакции
        async with self._provider.transaction():
            result = None
            for op in operations:
                result = await op()
            return result
    
    async def close(self) -> None:
        """Закрыть соединение."""
        await self._provider.shutdown()


class SQLiteAdapter(DatabasePort):
    """
    Адаптер SQLite для DatabasePort.
    
    ОБЁРТКА вокруг sqlite3 для работы через порт.
    Использует ThreadPoolExecutor для асинхронных операций.
    
    USAGE:
    ```python
    adapter = SQLiteAdapter("data/agent.db")
    await adapter.initialize()
    
    rows = await adapter.query("SELECT * FROM books WHERE id = ?", (1,))
    count = await adapter.execute("INSERT INTO logs (msg) VALUES (?)", ("test",))
    ```
    """
    
    def __init__(self, database_path: str):
        """
        ARGS:
        - database_path: Путь к файлу БД SQLite
        """
        import sqlite3
        from concurrent.futures import ThreadPoolExecutor
        
        self._database_path = database_path
        self._conn = None
        self._sqlite3 = sqlite3
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='sqlite')
    
    async def initialize(self) -> None:
        """Инициализация соединения."""
        import asyncio
        
        loop = asyncio.get_event_loop()
        self._conn = await loop.run_in_executor(
            self._executor,
            lambda: self._sqlite3.connect(self._database_path)
        )
        self._conn.row_factory = self._sqlite3.Row
    
    def _run_in_executor(self, func, *args):
        """Запустить функцию в executor."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._executor, func, *args)
    
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполнить SELECT запрос.
        
        SQLite использует ? для параметров, а не именованные параметры.
        """
        if self._conn is None:
            await self.initialize()
        
        # Конвертируем именованные параметры в позиционные
        param_values = None
        if params:
            if isinstance(params, dict):
                param_values = list(params.values())
            elif isinstance(params, (list, tuple)):
                param_values = tuple(params)  # SQLite требует кортеж
            else:
                param_values = params
        
        def _execute_query():
            # SQLite не принимает None как параметры - передаём пустой кортеж
            pvals = param_values if param_values is not None else ()
            cursor = self._conn.execute(sql, pvals)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        return await self._run_in_executor(_execute_query)
    
    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Выполнить INSERT/UPDATE/DELETE запрос.
        """
        if self._conn is None:
            await self.initialize()
        
        # Конвертируем именованные параметры в позиционные
        param_values = None
        if params:
            if isinstance(params, dict):
                param_values = list(params.values())
            elif isinstance(params, (list, tuple)):
                param_values = tuple(params)  # SQLite требует кортеж
            else:
                param_values = params
        
        def _execute_update():
            # SQLite не принимает None как параметры - передаём пустой кортеж
            pvals = param_values if param_values is not None else ()
            cursor = self._conn.execute(sql, pvals)
            self._conn.commit()
            return cursor.rowcount
        
        return await self._run_in_executor(_execute_update)
    
    async def transaction(
        self,
        operations: List[Callable[[], Awaitable[Any]]]
    ) -> Any:
        """
        Выполнить операции в транзакции.
        
        ВАЖНО: SQLite требует чтобы все операции в транзакции
        выполнялись в том же потоке где создано соединение.
        """
        if self._conn is None:
            await self.initialize()
        
        # Выполняем все операции в том же потоке где connection
        def _run_transaction():
            result = None
            try:
                for op in operations:
                    # Для SQLite операций нужно использовать тот же executor
                    # Это упрощённая реализация - для полной поддержки
                    # нужно передавать SQL операции а не coroutine
                    raise NotImplementedError(
                        "Transaction requires SQL-based operations for SQLite. "
                        "Use execute() directly instead."
                    )
                self._conn.commit()
                return result
            except Exception:
                self._conn.rollback()
                raise
        
        return await self._run_in_executor(_run_transaction)
    
    async def close(self) -> None:
        """Закрыть соединение."""
        if self._conn:
            def _close():
                self._conn.close()
            
            await self._run_in_executor(_close)
            self._conn = None
        
        self._executor.shutdown(wait=False)
