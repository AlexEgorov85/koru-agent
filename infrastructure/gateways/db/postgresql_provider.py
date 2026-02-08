"""
PostgreSQLProvider - реализация DB-провайдера для PostgreSQL.
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from domain.abstractions.event_types import EventType
from infrastructure.gateways.database_providers.base_provider import BaseDBProvider, DatabaseHealthStatus


class PostgreSQLProvider(BaseDBProvider):
    """
    Реализация DB-провайдера для PostgreSQL.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (шлюз)
    - Зависимости: от базового класса BaseDBProvider
    - Ответственность: интеграция с PostgreSQL базой данных
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self, connection_string: str, config: Dict[str, Any]):
        """
        Инициализация PostgreSQL провайдера.
        
        Args:
            connection_string: Строка подключения к PostgreSQL
            config: Конфигурация провайдера
        """
        super().__init__(connection_string, config)
        self._pool = None
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.min_connections = config.get("min_connections", 1)
        self.max_connections = config.get("max_connections", 10)
    
    async def initialize(self) -> bool:
        """
        Инициализация пула соединений с PostgreSQL.
        
        Returns:
            bool: Успешность инициализации
        """
        try:
            # Импортируем asyncpg только при необходимости
            import asyncpg
            
            # Создаем пул соединений
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections
            )
            
            # Проверяем подключение
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            self._is_connected = True
            self.health_status = DatabaseHealthStatus.HEALTHY
            
            return True
        except Exception as e:
            if hasattr(self, 'event_publisher') and self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    "PostgreSQLProvider",
                    {
                        "message": f"Ошибка инициализации PostgreSQLProvider: {str(e)}",
                        "error": str(e),
                        "context": "initialization_error"
                    }
                )
            self.health_status = DatabaseHealthStatus.UNHEALTHY
            return False
    
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера и освобождение ресурсов.
        """
        if self._pool:
            await self._pool.close()
        self._is_connected = False
        self.health_status = DatabaseHealthStatus.UNKNOWN
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Выполнение SQL-запроса к PostgreSQL.
        
        Args:
            query: SQL-запрос
            params: Параметры запроса
            
        Returns:
            List[Dict[str, Any]]: Результаты запроса
        """
        if not self._is_connected:
            if not await self.initialize():
                raise RuntimeError("PostgreSQLProvider не инициализирован")
        
        start_time = time.time()
        
        try:
            async with self._pool.acquire() as conn:
                # Если параметры переданы как словарь, преобразуем в кортеж значений
                if params:
                    if isinstance(params, dict):
                        # Для именованных параметров используем **params
                        result = await conn.fetch(query, **params)
                    else:
                        # Для позиционных параметров используем *params
                        result = await conn.fetch(query, *params)
                else:
                    result = await conn.fetch(query)
                
                # Преобразуем результат в список словарей
                rows = [dict(row) for row in result]
                
                # Обновляем метрики
                self._update_metrics(time.time() - start_time)
                
                return rows
        except Exception as e:
            # Обновляем метрики ошибки
            self._update_metrics(time.time() - start_time, success=False)
            raise e
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности PostgreSQL провайдера.
        
        Returns:
            Dict[str, Any]: Статус работоспособности
        """
        if not self._is_connected:
            return {
                "status": DatabaseHealthStatus.UNHEALTHY.value,
                "error": "Provider not connected",
                "database": self.database
            }
        
        try:
            start_time = time.time()
            
            # Выполняем простой запрос для проверки соединения
            async with self._pool.acquire() as conn:
                result = await conn.fetchval("SELECT version();")
            
            response_time = time.time() - start_time
            
            return {
                "status": DatabaseHealthStatus.HEALTHY.value,
                "database": self.database,
                "server_version": result,
                "response_time_ms": response_time * 1000,
                "is_connected": self._is_connected,
                "query_count": self.query_count,
                "error_count": self.error_count,
                "avg_query_time_ms": self.avg_query_time * 1000
            }
        except Exception as e:
            return {
                "status": DatabaseHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "database": self.database,
                "is_connected": self._is_connected
            }
    
    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для работы с транзакциями.
        
        Yields:
            Connection: Соединение с базой данных в рамках транзакции
        """
        if not self._is_connected:
            raise RuntimeError("PostgreSQLProvider не инициализирован")
        
        conn = await self._pool.acquire()
        trans = conn.transaction()
        
        try:
            await trans.start()
            yield conn
            await trans.commit()
        except Exception:
            await trans.rollback()
            raise
        finally:
            await self._pool.release(conn)
    
    async def execute_many(self, query: str, params_list: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Выполнение одного запроса с множеством наборов параметров.
        
        Args:
            query: SQL-запрос
            params_list: Список словарей параметров для выполнения запроса
            
        Returns:
            List[List[Dict[str, Any]]]: Результаты для каждого набора параметров
        """
        if not self._is_connected:
            if not await self.initialize():
                raise RuntimeError("PostgreSQLProvider не инициализирован")
        
        results = []
        for params in params_list:
            result = await self.execute_query(query, params)
            results.append(result)
        
        return results