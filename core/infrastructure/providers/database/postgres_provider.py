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
        # event_bus_logger инициализируется в BaseProvider.initialize()

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация пула соединений.
        """
        try:
            # Инициализация event_bus_logger если ещё не создан
            if self.event_bus_logger is None:
                from core.infrastructure.event_bus.unified_event_bus import get_event_bus
                from core.infrastructure.logging import EventBusLogger
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                try:
                    event_bus = get_event_bus()
                    self.event_bus_logger = EventBusLogger(event_bus, "system", "db_provider", self.name)
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                except:
                    self.event_bus_logger = type('obj', (object,), {
                        'info': lambda *args, **kwargs: None,
                        'debug': lambda *args, **kwargs: None,
                        'warning': lambda *args, **kwargs: None,
                        'error': lambda *args, **kwargs: None
                    })()

            await self.event_bus_logger.info(f"Создание пула соединений с PostgreSQL: {self.config.host}:{self.config.port}/{self.config.database}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
                await self.event_bus_logger.info(f"Подключено к PostgreSQL: {version}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            self.is_initialized = True
            self.health_status = DBHealthStatus.HEALTHY
            self.last_health_check = time.time()

            init_time = time.time() - start_time
            await self.event_bus_logger.info(f"PostgreSQL провайдер успешно инициализирован за {init_time:.2f} секунд")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            return True

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка инициализации PostgreSQL провайдера: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
            await self.event_bus_logger.warning("Обнаружено мёртвое подключение, пересоздаю пул...")
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
                    await self.event_bus_logger.info("Завершение работы пула соединений PostgreSQL...")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.pool.close()
                    self.pool = None

                self.is_initialized = False
                await self.event_bus_logger.info("PostgreSQL провайдер успешно завершил работу")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка при завершении работы PostgreSQL провайдера: {str(e)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
                    self.pool.release(conn)

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
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
        await self.event_bus_logger.info(f"[DB_DEBUG] execute_query вызван с query={query}, params={params}")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        try:
            conn = await self._acquire_valid_connection()
            try:
                # [DB_DEBUG] 3.2. Выполнение запроса
                await self.event_bus_logger.debug(f"Выполнение SQL: {query}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.debug(f"Params: {params}, type: {type(params)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                await self.event_bus_logger.info(f"[DB_DEBUG] выполнение запроса...")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                # Логируем запрос при необходимости
                await self.event_bus_logger.debug(f"Executing query: {query}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                if params:
                    await self.event_bus_logger.debug(f"Query params: {params}")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
                        await self.event_bus_logger.debug(f"After replacing {i+1}: {converted_query}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.debug(f"Final query: {converted_query}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
                await self.event_bus_logger.info(f"[DB_DEBUG] запрос выполнен, rows={len(rows) if rows else 0}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
                await self.event_bus_logger.info(f"[DB_DEBUG] возвращаем DBQueryResult: success={query_result.success}, error={query_result.error}, rows={len(query_result.rows)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                # Обновляем метрики
                self._update_metrics(query_result.execution_time)

                return query_result
            finally:
                # Освобождаем подключение обратно в пул
                if self.pool:
                    self.pool.release(conn)

        except Exception as e:
            # [DB_DEBUG] 3.2. Исключение при выполнении
            await self.event_bus_logger.error(f"[DB_DEBUG] исключение при выполнении запроса: {e}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error(f"Ошибка выполнения запроса: {str(e)}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error(f"Query was: {query}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            if params:
                await self.event_bus_logger.error(f"Params were: {params}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
            await self.event_bus_logger.info(f"[DB_DEBUG] возвращаем DBQueryResult: success={error_result.success}, error={error_result.error}, rows={len(error_result.rows)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
                self.pool.release(conn)

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
                    self.pool.release(conn)

        except Exception as e:
            self.event_bus_logger.error(f"Ошибка выполнения запроса: {str(e)}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self._update_metrics(time.time() - start_time, success=False)
            raise

    async def close(self) -> None:
        """Закрыть соединение (для совместимости с DatabaseInterface)."""
        await self.shutdown()


# Alias для совместимости с фабрикой
PostgresProvider = PostgreSQLProvider