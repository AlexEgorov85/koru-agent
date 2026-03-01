"""
Провайдер для PostgreSQL.
Использует asyncpg для асинхронной работы с PostgreSQL.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union
from contextlib import asynccontextmanager

import asyncpg

from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.models.types.db_types import DBConnectionConfig, DBHealthStatus, DBQueryResult


logger = logging.getLogger(__name__)


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

        self.event_bus_logger.info(f"Инициализация PostgreSQL провайдера для базы: {self.config.database}")

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация пула соединений.
        """
        try:
            self.event_bus_logger.info(f"Создание пула соединений с PostgreSQL: {self.config.host}:{self.config.port}/{self.config.database}")
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
                self.event_bus_logger.info(f"Подключено к PostgreSQL: {version}")

            self.is_initialized = True
            self.health_status = DBHealthStatus.HEALTHY
            self.last_health_check = time.time()

            init_time = time.time() - start_time
            self.event_bus_logger.info(f"PostgreSQL провайдер успешно инициализирован за {init_time:.2f} секунд")

            return True

        except Exception as e:
            logger.exception(f"Ошибка инициализации PostgreSQL провайдера: {str(e)}")
            self.health_status = DBHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """
        Корректное завершение работы пула соединений.
        """
        async with self._lock:
            try:
                if self.pool:
                    self.event_bus_logger.info("Завершение работы пула соединений PostgreSQL...")
                    await self.pool.close()
                    self.pool = None

                self.is_initialized = False
                self.event_bus_logger.info("PostgreSQL провайдер успешно завершил работу")

            except Exception as e:
                self.event_bus_logger.error(f"Ошибка при завершении работы PostgreSQL провайдера: {str(e)}")

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
            async with self.pool.acquire() as conn:
                # Проверяем доступность базы данных
                result = await conn.fetchrow("""
                    SELECT
                        current_database() as database,
                        current_user as user,
                        now() as timestamp
                """)

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
            self.event_bus_logger.error(f"Ошибка health check для PostgreSQL: {str(e)}")
            return {
                "status": DBHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "database": self.config.database,
                "is_initialized": self.is_initialized
            }

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Выполнить SQL-запрос.
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                # Логируем запрос при необходимости
                if logger.isEnabledFor(logging.DEBUG):
                    self.event_bus_logger.debug(f"Executing query: {query}")
                    if params:
                        self.event_bus_logger.debug(f"Query params: {params}")

                # Выполняем запрос
                if params:
                    if isinstance(params, dict):
                        # Если параметры переданы как словарь, извлекаем значения в правильном порядке
                        param_values = [params[key] for key in sorted(params.keys())]
                        result = await conn.fetch(query, *param_values)
                    elif isinstance(params, (list, tuple)):
                        # Если параметры переданы как список или кортеж, передаем напрямую
                        result = await conn.fetch(query, *params)
                    else:
                        # В противном случае, передаем без параметров
                        result = await conn.fetch(query)
                else:
                    result = await conn.fetch(query)

                # Обрабатываем результат как список словарей
                rows = [dict(row) for row in result]
                return rows

        except Exception as e:
            self.event_bus_logger.error(f"Ошибка выполнения запроса: {str(e)}")
            self.event_bus_logger.error(f"Query was: {query}")
            if params:
                self.event_bus_logger.error(f"Params were: {params}")
            raise

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> DBQueryResult:
        """
        Выполнение SQL запроса.
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                # Логируем запрос при необходимости
                if logger.isEnabledFor(logging.DEBUG):
                    self.event_bus_logger.debug(f"Executing query: {query}")
                    if params:
                        self.event_bus_logger.debug(f"Query params: {params}")

                # Выполняем запрос
                if params:
                    if isinstance(params, dict):
                        # Если параметры переданы как словарь, извлекаем значения в правильном порядке
                        param_values = [params[key] for key in sorted(params.keys())]
                        result = await conn.fetch(query, *param_values)
                    elif isinstance(params, (list, tuple)):
                        # Если параметры переданы как список или кортеж, передаем напрямую
                        result = await conn.fetch(query, *params)
                    else:
                        # В противном случае, передаем без параметров
                        result = await conn.fetch(query)
                else:
                    result = await conn.fetch(query)

                # Обрабатываем результат
                rows = [dict(row) for row in result]
                columns = list(rows[0].keys()) if rows else []

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

                # Обновляем метрики
                self._update_metrics(query_result.execution_time)

                return query_result

        except Exception as e:
            self.event_bus_logger.error(f"Ошибка выполнения запроса: {str(e)}")
            self.event_bus_logger.error(f"Query was: {query}")
            if params:
                self.event_bus_logger.error(f"Params were: {params}")

            self._update_metrics(time.time() - start_time, success=False)

            return DBQueryResult(
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

    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для транзакций.
        """
        if not self.is_initialized or not self.pool:
            await self.initialize()

        async with self.pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            try:
                yield conn
                await tx.commit()
            except Exception as e:
                await tx.rollback()
                raise


# Alias для совместимости с фабрикой
PostgresProvider = PostgreSQLProvider