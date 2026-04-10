"""
Провайдер для PostgreSQL.
Использует asyncpg для асинхронной работы с PostgreSQL.
"""
import asyncio
import time
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable
from contextlib import asynccontextmanager

import asyncpg

from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.models.types.db_types import DBConnectionConfig, DBHealthStatus, DBQueryResult
from core.infrastructure.logging.event_types import LogEventType


class PostgreSQLProvider(BaseDBProvider):
    """
    Провайдер для PostgreSQL с использованием asyncpg.
    Обеспечивает асинхронный доступ к базе данных.
    """

    def __init__(self, config: Union[Dict[str, Any], DBConnectionConfig]):
        """
        Инициализация PostgreSQL провайдера.
        :param config: Конфигурация подключения
        """
        super().__init__(config)
        self.pool = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация пула соединений.
        """
        try:
            self.log.info("Создание пула соединений с PostgreSQL: %s:%s/%s", self.config.host, self.config.port, self.config.database, extra={"event_type": LogEventType.SYSTEM_INIT})
            start_time = time.time()

            # Создаем пул соединений
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                ssl=self.config.sslmode if self.config.sslmode != "disable" else None,
                timeout=self.config.timeout,
                min_size=1,
                max_size=self.config.pool_size,
                command_timeout=self.config.timeout,
                server_settings={
                    "application_name": "agent_system",
                }
            )

            # Проверяем подключение
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                self.log.info("Подключено к PostgreSQL: %s", version, extra={"event_type": LogEventType.SYSTEM_INIT})

            self.is_initialized = True
            self.health_status = DBHealthStatus.HEALTHY
            self.last_health_check = time.time()

            init_time = time.time() - start_time
            self.log.info("PostgreSQL провайдер успешно инициализирован за %.2f секунд", init_time, extra={"event_type": LogEventType.SYSTEM_INIT})

            return True

        except Exception as e:
            self.log.error("Ошибка инициализации PostgreSQL провайдера: %s", str(e), extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            self.health_status = DBHealthStatus.UNHEALTHY
            return False

    async def _acquire_valid_connection(self):
        """
        Получить валидное подключение из пула с проверкой жизнеспособности.
        Если подключение мертво, автоматически пересоздаёт пул.
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        try:
            conn = await self.pool.acquire()
            # Быстрая проверка — пинг
            await conn.fetchval("SELECT 1")
            return conn
        except Exception:
            # Подключение мертво — пересоздаём пул
            self.log.warning("Обнаружено мёртвое подключение, пересоздаю пул...", extra={"event_type": LogEventType.WARNING})
            try:
                await self.pool.close()
            except Exception:
                pass
            self.pool = None
            self.is_initialized = False
            await self.initialize()
            # Возвращаем подключение из нового пула
            return await self.pool.acquire()

    async def shutdown(self) -> None:
        """
        Корректное завершение работы пула соединений.
        """
        async with self._lock:
            try:
                if self.pool:
                    self.log.info("Завершение работы пула соединений PostgreSQL...", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})
                    await self.pool.close()
                    self.pool = None

                self.is_initialized = False
                self.log.info("PostgreSQL провайдер успешно завершил работу", extra={"event_type": LogEventType.SYSTEM_SHUTDOWN})

            except Exception as e:
                self.log.error("Ошибка при завершении работы PostgreSQL провайдера: %s", str(e), extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья PostgreSQL провайдера.
        """
        try:
            if not self.is_initialized or not self.pool:
                return {
                    "status": DBHealthStatus.UNHEALTHY.value,
                    "error": "Pool not initialized"
                }

            # Проверяем работоспособность пула
            start_time = time.time()
            conn = await self._acquire_valid_connection()
            try:
                # Проверяем доступность базы данных
                result = await conn.fetchrow("""
                    SELECT
                        current_database() as database,
                        current_user as user,
                        now() as timestamp
                """)
            finally:
                if self.pool:
                    await self.pool.release(conn)

            response_time = time.time() - start_time

            return {
                "status": DBHealthStatus.HEALTHY.value,
                "database": result['database'],
                "user": result['user'],
                "timestamp": str(result['timestamp']),
                "response_time": response_time,
                "is_initialized": self.is_initialized,
                "query_count": self.query_count,
                "error_count": self.error_count
            }

        except Exception as e:
            self.log.error("Ошибка health check для PostgreSQL: %s", str(e), extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            return {
                "status": DBHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "database": self.config.database,
                "is_initialized": self.is_initialized
            }

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> DBQueryResult:
        """
        Выполнение SQL запроса (SELECT).
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        start_time = time.time()

        # [DB_DEBUG] 3.1. Входные параметры
        self.log.info("[DB_DEBUG] execute_query вызван с query=%s, params=%s",
                      query, params, extra={"event_type": LogEventType.DB_QUERY})

        try:
            conn = await self._acquire_valid_connection()
            try:
                # [DB_DEBUG] 3.2. Выполнение запроса
                self.log.debug("Выполнение SQL: %s", query, extra={"event_type": LogEventType.DB_QUERY})
                self.log.debug("Params: %s, type: %s", params, type(params), extra={"event_type": LogEventType.DB_QUERY})

                self.log.info("[DB_DEBUG] выполнение запроса...", extra={"event_type": LogEventType.DB_QUERY})

                # Логируем запрос при необходимости
                self.log.debug("Executing query: %s", query, extra={"event_type": LogEventType.DB_QUERY})
                if params:
                    self.log.debug("Query params: %s", params, extra={"event_type": LogEventType.DB_QUERY})

                # Выполняем запрос
                if params:
                    if isinstance(params, dict):
                        # Если параметры переданы как словарь, извлекаем значения в правильном порядке
                        # Сортируем по числовому значению (1, 2, 3...), не alphabetically!
                        # Ключи могут быть вида '1', '2' или 'p1', 'p2'
                        def sort_key(key):
                            try:
                                # Пробуем извлечь число напрямую (ключи '1', '2', ...)
                                return int(key)
                            except (ValueError, IndexError):
                                # Если не получилось, пробуем извлечь число из ключа вида 'p1', 'p2', etc.
                                try:
                                    return int(key[1:]) if key.startswith('p') else 0
                                except (ValueError, IndexError):
                                    return 0
                        param_values = [params[key] for key in sorted(params.keys(), key=sort_key)]
                        # Конвертируем %s в $1, $2, ... для asyncpg
                        converted_query = query
                        for i in range(len(param_values)):
                            converted_query = converted_query.replace('%s', f'${i+1}', 1)
                        result = await conn.fetch(converted_query, *param_values)
                    elif isinstance(params, (list, tuple)):
                        # Если параметры переданы как список или кортеж, передаем напрямую
                        # Конвертируем %s в $1, $2, ... для asyncpg
                        converted_query = query
                        for i in range(len(params)):
                            converted_query = converted_query.replace('%s', f'${i+1}', 1)
                        self.log.debug("After replacing %d: %s", i+1, converted_query, extra={"event_type": LogEventType.DB_QUERY})
                        self.log.debug("Final query: %s", converted_query, extra={"event_type": LogEventType.DB_QUERY})
                        result = await conn.fetch(converted_query, *params)
                    else:
                        # В противном случае, передаем без параметров
                        result = await conn.fetch(query)
                else:
                    result = await conn.fetch(query)

                # Обрабатываем результат
                rows = [dict(row) for row in result]
                columns = list(rows[0].keys()) if rows else []

                # [DB_DEBUG] 3.2. Результат выполнения
                self.log.info("[DB_DEBUG] запрос выполнен, rows=%d", len(rows) if rows else 0, extra={"event_type": LogEventType.DB_QUERY})

                # Создаем результат
                query_result = DBQueryResult(
                    success=True,
                    rows=rows,
                    rowcount=len(rows),
                    columns=columns,
                    execution_time=time.time() - start_time,
                    metadata={
                        "query": query,
                        "params": params,
                        "affected_rows": len(rows)
                    }
                )

                # [DB_DEBUG] 3.3. Возврат DBQueryResult
                self.log.info("[DB_DEBUG] возвращаем DBQueryResult: success=%s, error=%s, rows=%d",
                              query_result.success, query_result.error, len(query_result.rows),
                              extra={"event_type": LogEventType.DB_QUERY})

                # Обновляем метрики
                self._update_metrics(query_result.execution_time)

                return query_result
            finally:
                # Освобождаем подключение обратно в пул
                if self.pool:
                    await self.pool.release(conn)

        except Exception as e:
            # [DB_DEBUG] 3.2. Исключение при выполнении
            self.log.error("[DB_DEBUG] исключение при выполнении запроса: %s", str(e),
                           extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            self.log.error("Ошибка выполнения запроса: %s", str(e), extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            self.log.error("Query was: %s", query, extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            if params:
                self.log.error("Params were: %s", params, extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)

            self._update_metrics(time.time() - start_time, success=False)

            # [DB_DEBUG] 3.3. Возврат DBQueryResult (ошибка)
            error_result = DBQueryResult(
                success=False,
                rows=[],
                rowcount=-1,
                columns=[],
                error=str(e),
                execution_time=time.time() - start_time,
                metadata={
                    "query": query,
                    "params": params,
                    "error_type": type(e).__name__
                }
            )
            self.log.info("[DB_DEBUG] возвращаем DBQueryResult: success=%s, error=%s, rows=%d",
                          error_result.success, error_result.error, len(error_result.rows),
                          extra={"event_type": LogEventType.DB_QUERY})
            return error_result

    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для транзакций.
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        conn = await self._acquire_valid_connection()
        try:
            tx = conn.transaction()
            await tx.start()
            try:
                yield conn
                await tx.commit()
            except Exception as e:
                await tx.rollback()
                raise
        finally:
            if self.pool:
                await self.pool.release(conn)

    # Методы для совместимости с DatabaseInterface
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Выполнить SELECT запрос (для совместимости с DatabaseInterface)."""
        result = await self.execute_query(sql, params)
        return result

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Выполнить INSERT/UPDATE/DELETE запрос (для совместимости с DatabaseInterface).
        Возвращает количество затронутых строк.
        """
        # Для INSERT/UPDATE/DELETE используем execute_single для получения rowcount
        if not self.is_initialized or not self.pool:
            await self.initialize()

        start_time = time.time()
        try:
            conn = await self._acquire_valid_connection()
            try:
                if params:
                    if isinstance(params, dict):
                        param_values = [params[key] for key in sorted(params.keys())]
                        result = await conn.execute(sql, *param_values)
                    elif isinstance(params, (list, tuple)):
                        result = await conn.execute(sql, *params)
                    else:
                        result = await conn.execute(sql)
                else:
                    result = await conn.execute(sql)

                # parse rowcount from result string like "INSERT 0 1"
                parts = result.split()
                rowcount = int(parts[-1]) if parts else 0

                self._update_metrics(time.time() - start_time)
                return rowcount
            finally:
                if self.pool:
                    await self.pool.release(conn)

        except Exception as e:
            self.log.error("Ошибка выполнения запроса: %s", str(e), extra={"event_type": LogEventType.DB_ERROR}, exc_info=True)
            self._update_metrics(time.time() - start_time, success=False)
            raise

    async def close(self) -> None:
        """Закрыть соединение (для совместимости с DatabaseInterface)."""
        await self.shutdown()


# Alias для совместимости с фабрикой
PostgresProvider = PostgreSQLProvider
