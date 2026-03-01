"""
Mock DB Provider для тестирования без реального подключения к БД.
"""
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.models.types.db_types import DBConnectionConfig, DBHealthStatus, DBQueryResult


logger = logging.getLogger(__name__)


class MockDBProvider(BaseDBProvider):
    """
    Mock DB провайдер для тестирования.
    """

    def __init__(self, config: DBConnectionConfig):
        super().__init__(config)
        self.is_initialized = False
        self.event_bus_logger.info(f"Создан MockDBProvider для базы: {self.config.database}")

    async def initialize(self) -> bool:
        """Инициализация провайдера."""
        try:
            self.event_bus_logger.info(f"Mock DB провайдер инициализирован для базы: {self.config.database}")
            self.is_initialized = True
            return True
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка инициализации MockDBProvider: {str(e)}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности провайдера."""
        return {
            "status": DBHealthStatus.HEALTHY.value,
            "database": self.config.database,
            "is_initialized": self.is_initialized
        }

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Выполнить SQL-запрос (заглушка)."""
        if not self.is_initialized:
            await self.initialize()

        self.event_bus_logger.debug(f"Mock выполнение запроса: {query}")

        # Возвращаем mock-результат в виде списка словарей
        return [{"test": 1}]  # Простой тестовый результат

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> DBQueryResult:
        """Выполнение SQL запроса (заглушка)."""
        if not self.is_initialized:
            await self.initialize()

        self.event_bus_logger.debug(f"Mock выполнение запроса: {query}")

        # Возвращаем mock-результат
        mock_result = DBQueryResult(
            success=True,
            rows=[{"test": 1}],  # Простой тестовый результат
            rowcount=1,
            columns=["test"],
            execution_time=0.001,
            metadata={
                "query": query,
                "params": params
            }
        )

        # Обновляем метрики
        self._update_metrics(mock_result.execution_time)

        return mock_result

    @asynccontextmanager
    async def transaction(self):
        """Контекстный менеджер для транзакций (заглушка)."""
        if not self.is_initialized:
            await self.initialize()

        # Возвращаем mock-соединение
        yield self

    async def shutdown(self):
        """Завершение работы провайдера."""
        self.event_bus_logger.info("Mock DB провайдер завершает работу")
        self.is_initialized = False


# Alias для совместимости с фабрикой
SQLiteProvider = MockDBProvider